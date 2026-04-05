from settings import *  # definitions of all constants used in the code
from pin_assignments import *
from machine import Pin, I2C
import time
from sys import exit
import _thread
from fastlog2 import fast_log2
from array import array
from mydacs import send_dac_value, dac_setup, ADDRESS_MANAGER, prepare_tune_latch, DacMessages
#from wavecount_table import NOTE_WAVECOUNTS  # use this to give the tuning PIDs a target
# this table actually contains the log2s of the wave counts

from freq_measure import get_sample, get_sample_mean, freq_counter_cleanup, ema_reset, flush_pio
from wavecount_table import NOTE_WAVECOUNTS, VoltageArrays

from line_fitter_fixedpoint import FitterFP
from pidcontroller import PidController
FITTER = FitterFP(4)  # todo - this should belong to a voice

"""

# DAC setup code

for x in range(VOICE_COUNT):
    ADDRESS_MANAGER.put(x)
    time.sleep(0.1)
    dac_setup()  # manages reset pin
"""

################### TESTING SETUP CODE #######################

cnt = 0
loopcount = 0
loopstart = time.ticks_ms()

ADDRESS_MANAGER.put(0)
time.sleep(0.1)
dac_setup()  # manages reset pin
prepare_tune_latch()
send_dac_value(4, 80)
send_dac_value(5, 0)

################### END OF SETUP FUNCTIONS #######################


def initial_tune():

    """Establishes the linear fit of CV to log2(f). Need one of these fitter objects per oscillator."""
    # TODO: make part of voice class

    send_dac_value(5, 0)  # fine voltage = 0 for calibration

    for q in range(12,255,64):  # 4 steps across the whole voltage range
        send_dac_value(4, q)
        time.sleep(0.01)
        flush_pio()
        ema_reset()
        r = None
        while not r:
            r = get_sample_mean()
        FITTER.add(q, fast_log2(r))


    FITTER.fit_line()


initial_tune()
print("fitted initial line")



TARGET_WAVECOUNTS = array("I", [0] * 4)  # for communication between cores. Voice # and what log2(f) it aims at
# array positions 4 and 5 unused (VCO coarse and fine - these are managed by the PID)
DAC_DIRTY = 0  # "dirty flag" for each channel of each voice. Only update if the flag = 1. 32 bits.
VOICE_DIRTY = 0  # as above for whether a voice changed note. Used to determine what we should retune.
VOLTAGE_ARRAYS = VoltageArrays()  # store and retrieve coarse, fine values per note per voice
DAC_MESSAGES = DacMessages()  # manages values to be written to the DACs
RUNNING = False


######### Temporary things for data logging ###########
TIMES = array("I", [0] * 6096)
EXPECTEDS = array("I", [0] * 6096)
FREQS = array("i", [0] * 6096)
######### Temporary things for data logging ###########

def fast_loop():

    global TARGET_WAVECOUNTS  # so we know what we are aiming for
    global DAC_MESSAGES
    global DAC_DIRTY
    global VOLTAGE_ARRAYS
    global DAC_MESSAGES
    global RUNNING  # flag used to stop this thread from the main thread

    # initial variable setup before entering loop
    pid = PidController(6144, 32, 0)  # used for all voices
    # 500 200 100 with squared pid
    tnow = time.ticks_us()
    last_pid_time = time.ticks_us()
    convergence_possible = 0  # a counter for how many samples we got within the error tolerance. Past the threshold,
    # we consider the note tuned and move on.
    convergence_threshold = 4  # how many good samples before we consider the note stabilized and tuned
    converged = False
    voice_address = 0  # the current voice we are sending DAC signals to
    sampled_voice = 0  # address of voice whose frequency we are reading
    sample_count = 8  # how many samples do we aim to record for this note? More for higher freqs
    error_ema = 999  # smoothed error for measuring played note
    coarse = 0  # signals to send to the DAC
    fine = 0

    #######
    target_note = 0
    sample_count = 0  # may as well get more samples for hi freqs, as they come faster
    #####

    print("fast loop function starting")

    ######### Temporary things for data logging ###########
    global data_idx
    data_idx = 0
    ######### Temporary things for data logging ###########

    while RUNNING:

        # calculate how long it has been since we were last here. Don't want to send DAC corrections too fast.
        tlast =  tnow
        tnow = time.ticks_us()
        loop_time = time.ticks_diff(tnow, tlast)
        tlast = tnow
        ##################################

        if not TARGET_WAVECOUNTS[0] == target_note:  # naively check for change every time rn
            target_note = TARGET_WAVECOUNTS[0]  #  todo: manage this for multi voice
            sample_count = (target_note >> 13) * -6 + 46
            converged = False
            convergence_possible = 0
            predicted_v = FITTER.getx(target_note)  # todo - use voltage arrays

            coarse = predicted_v >> 8
            fine = predicted_v & 255

            ############################
            send_dac_value(4, coarse)
            send_dac_value(5, fine)
            time.sleep(0.001)
            ############################

            pid.reset()
            flush_pio()
            ema_reset(target_note)
            error_ema = 999

        sample = None
        while not sample:
            sample = get_sample(sample_count)  # now returns the fast log2

        error = target_note - sample
        if error < 0:
            error = -1 * error

        # determine how close we are getting to the target, and break out of tuning this note if possible
        if error < 100:
            convergence_possible += 1
            error_ema = ((ERROR_EMA_ALPHA * error) >> 12) + (((4096 - ERROR_EMA_ALPHA) * error_ema) >> 12)
            if error_ema < 20 and convergence_possible > convergence_threshold:
                converged = True
        else:
            convergence_possible = 0  # reset to start, need 4 continuous good measurements

        if not converged:  # we still need to get corrections
            if time.ticks_diff(tnow, last_pid_time) > MINIMUM_PID_INTERVAL:
                last_pid_time = tnow
                correction = pid.get_correction(sample - target_note)  # todo: tidy up so we use the error calc
                fine += correction

                # if fine has exceeded the range 0 to 255 we need to send a coarse adjustment instead, and then
                # send the remainder as the fine adjustment
                if 0 < fine < 255:
                    pass  # do nothing and just send fine as normal
                elif fine < 0:
                    fine *= -1
                    coarse -= (fine // 255) + 1
                    fine = 255 - (fine % 255)
                    DAC_MESSAGES.set(voice_address, 4, coarse)

                elif fine > 255:
                    coarse += fine // 255
                    fine = fine % 255
                    DAC_MESSAGES.set(voice_address, 4, coarse)

                # write the correction into the DAC message queue to be sent out like all the other voltages
                DAC_MESSAGES.set(voice_address, 5, fine)

        # corrections are now applied, send all the voltages to the voice - oscillator values + CVs from main thread
        todo = DAC_MESSAGES.get_dirty(voice_address)  # only update the values that have changed
        # this is a number where each bit denotes the DAC channel to be updated
        chan = 0
        while todo:
            if todo & 1:
                val = DAC_MESSAGES.get(voice_address, chan)
                send_dac_value(chan, val)  # puts the message into the state machine FIFO
            todo >>= 1
            chan += 1

        ######### Temporary things for data logging ###########
        TIMES[data_idx] = tnow
        EXPECTEDS[data_idx] = target_note
        FREQS[data_idx] = sample
        data_idx += 1
        ######### Temporary things for data logging ###########


def shut_down():

    global RUNNING

    RUNNING = False

    print("Shutting down...")
    #print("count", loopcount)
    #total_time = time.ticks_diff(time.ticks_ms(), loopstart)

    #lps = loopcount / total_time * 1000
    #print(f"Averaged {lps} loops per second over {total_time} ms.")
    freq_counter_cleanup()
    send_dac_value(2, 0)
    print("VCA muted")
    time.sleep(1)  # make sure other core has time to exit
    print("Shutdown function finished")

    with open("result.txt", "w") as f:
        cnt = 0
        for x, y, z in zip(TIMES, FREQS, EXPECTEDS):
            f.write(f"{str(x)}\t{str(y)}\t{str(z)}")
            f.write("\n")
            cnt += 1
            if cnt == 4096:
                break
    print("wrote data")

    exit()




import random

global data_idx
data_idx = 0
RUNNING = True
TARGET_WAVECOUNTS[0] = NOTE_WAVECOUNTS[46]
_thread.start_new_thread(fast_loop, ())

send_dac_value(2, 127)

time.sleep(1)  # give time for PIO to start working!?

lc = 0


try:
    note = 47
    while data_idx < 4096:  # wait for fast loop to fill up measurement arrays
        lc += 1

        #print(data_idx)
        if lc % 50 == 0:
            TARGET_WAVECOUNTS[0] = NOTE_WAVECOUNTS[note]
            note += 1
            if note > 95:
                note = 47

        time.sleep(0.01)

except Exception as e:
    print(repr(e))

finally:
    #total_time = time.ticks_diff(time.ticks_ms(), loopstart)
    #lps = loopcount / total_time * 1000
    #print(f"Averaged {lps} loops per second over {total_time} ms.")
    print("finally block")
    shut_down()




