from custom_fifo import CustomFIFO
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

from freq_measure import get_sample, get_sample_mean, freq_counter_cleanup, ema_reset, flush_pio, get_sample_mean_float
from wavecount_table import NOTE_WAVECOUNTS, NOTES, VoltageArrays

from line_fitter_fixedpoint import FitterFP
from pidcontroller import PidController

from tuningarrays import TuningArrays
from readmidi import MidiReader


# DAC setup code

for x in range(VOICE_COUNT):
    ADDRESS_MANAGER.put(x)
    time.sleep(0.1)
    dac_setup()  # manages reset pin


################### TESTING SETUP CODE #######################

cnt = 0
loopcount = 0
loopstart = time.ticks_ms()

"""
ADDRESS_MANAGER.put(0)
time.sleep(0.1)
dac_setup()  # manages reset pin
prepare_tune_latch()

ADDRESS_MANAGER.put(1)
time.sleep(0.1)
dac_setup()  # manages reset pin
"""
################### END OF SETUP FUNCTIONS #######################




DAC_MESSAGES = DacMessages()  # manages values to be written to the DACs
RUNNING = False
NOTE_QUEUE = CustomFIFO(size=8)  # new notes we want to play. upper 4 bits: voice address, lower 8: MIDI note number

######### Temporary things for data logging ###########
TIMES = array("I", [0] * 6096)
EXPECTEDS = array("I", [0] * 6096)
FREQS = array("i", [0] * 6096)


######### Temporary things for data logging ###########

def fast_loop():

    global TARGET_WAVECOUNTS  # so we know what we are aiming for
    global DAC_MESSAGES
    global VOLTAGE_ARRAYS
    global DAC_MESSAGES
    global RUNNING  # flag used to stop this thread from the main thread
    global NOTE_QUEUE
    global get_sample

    # initial variable setup before entering loop
    pid = PidController(6144, 32, 0)  # used for all voices
    # 500 200 100 with squared pid
    tnow = time.ticks_us()
    last_pid_time = time.ticks_us()
    convergence_possible = 0  # a counter for how many samples we got within the error tolerance. Past the threshold,
    # we consider the note tuned and move on.
    convergence_threshold = 2  # how many good samples before we consider the note stabilized and tuned
    converged = True  # start as true so we will grab the first note from the note queue
    sampled_voice = 0  # address of voice whose frequency we are reading
    sampled_voice_changed = False
    sample_count = 4  # how many samples do we aim to record for this note? More for higher freqs
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

        new_note = NOTE_QUEUE.get()
        if new_note:  # set up tuning of the new note
            print(new_note)
            midinote = new_note & 255
            voice = new_note >> 8
            voltages = TUNING_ARRAYS.get(voice, midinote)
            coarse = voltages >> 8
            fine = voltages & 255

            DAC_MESSAGES.set(sampled_voice, 4, coarse)
            DAC_MESSAGES.set(sampled_voice, 5, fine)

        sample = None

        while not sample:  # wait for sample which will always be pretty fast
            sample = get_sample(sample_count)  # now returns the fast log2

        for v in (0,1,2,3):  # apparently faster than using a range object

            todo = DAC_MESSAGES.get_dirty(v)  # only update the values that have changed
            # this is a number where each bit denotes the DAC channel to be updated
            #print(todo)

            if todo:  # need to send the messages to this DAC, if not to do then we will skip the while loop, send nowt
                ADDRESS_MANAGER.put(v)

            chan = 0
            while todo:
                if todo & 1:
                    val = DAC_MESSAGES.get(v, chan)
                    #print(f"sending {val} to {chan} on dac {v}")
                    send_dac_value(chan, val)  # puts the message into the state machine FIFO
                todo >>= 1
                chan += 1


def shut_down():

    global RUNNING

    DAC_MESSAGES.set(0, 2, 0)
    DAC_MESSAGES.set(1, 2, 0)

    RUNNING = False

    print("Shutting down...")
    #print("count", loopcount)
    #total_time = time.ticks_diff(time.ticks_ms(), loopstart)

    #lps = loopcount / total_time * 1000
    #print(f"Averaged {lps} loops per second over {total_time} ms.")
    freq_counter_cleanup()
    #send_dac_value(2, 0)
    print("VCA muted")
    time.sleep(1)  # make sure other core has time to exit
    print("Shutdown function finished")

    """

    with open("result.txt", "w") as f:
        cnt = 0
        for x, y, z in zip(TIMES, FREQS, EXPECTEDS):
            f.write(f"{str(x)}\t{str(y)}\t{str(z)}")
            f.write("\n")
            cnt += 1
            if cnt == 4096:
                break
    print("wrote data")
    
    """

    exit()



TUNING_ARRAYS = TuningArrays(VOICE_COUNT)
TUNING_ARRAYS.setup_arrays()

RUNNING = True
_thread.start_new_thread(fast_loop, ())

#

DAC_MESSAGES.set(0, 2, 127)


lc = 0


ADDRESS_MANAGER.put(0)
prepare_tune_latch()
#send_dac_value(2, 127)

sampled_notes = []
expected_notes = {}






# WARMUP LOOP:
import random
warmup_seconds = 1

print("warming up")
for x in range(warmup_seconds):
    time.sleep(1)
    a = random.randint(1, 254)
    b = random.randint(1, 254)
    send_dac_value(4, a)
    send_dac_value(5, b)

print("warmup done")

MR = MidiReader()

try:
    while 1:
        #print(TARGET_WAVETIME_ARRAY)
        #print("measured address ", MEASURED_ADDRESS)
        #print("top of main loop")
        #DAC_MANAGER.update()
        loopcount += 1
        #DISPLAY.draw_screen()
        MR.read()  # induce the MidiReader to compile messages to read out
        notes_queue = MR.get_messages("notes")
        controls_queue = MR.get_messages("controls")

        if len(notes_queue) > 1:
            #pass
            #print(notes_queue)
            pass

        if controls_queue:
            for msg in controls_queue:
                pass
                print(msg)
                if msg == (23, 254):  # temporary use of tap key to turn off
                    shut_down()
                #CONTROLS.process_control_signal(*msg)
                #ret = CONTROLS.get_updated()  # todo - careful we aren't discarding things
                #print(ret)
                #if not ret:
                    #continue  # should this be break?
                #for tup in ret:
                    #ob, parm, value = tup
                    #if parm:  # write the named variable of the specified object
                        # ob.__setattr__(parm, value)  # not this!!
                        #setattr(ob, parm, value)  # but this!!
                    #pair = DM.update(tup)  # get a new frame buffer for the LCD
                    #DISPLAY.update(pair)  # send the new frame buffer for display next loop

        for status, note in notes_queue:  # tuples of freq, true/false

            if status:  # True, want to play a new note
                try:
                    voice = 0  # todo multi voice
                except IndexError as e:
                    #print("no free voice available")
                    continue

                NOTE_QUEUE.put(note | (voice << 8))

            else:
                pass # un-play note



except Exception as e:
    print(repr(e))

finally:
    pass
    #shut_down()
