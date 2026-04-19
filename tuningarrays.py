from array import array
from pidcontroller import PidController
from line_fitter_fixedpoint import FitterFP
from mydacs import send_dac_value, ADDRESS_MANAGER, prepare_tune_latch
from freq_measure import flush_pio, ema_reset, get_sample_mean
from fastlog2 import fast_log2
import time
from wavecount_table import NOTE_WAVECOUNTS
from settings import *



class TuningArrays:

    def __init__(self, nvoices):

        """During the initial tuning, this class accesses the frequency measurement PIO directly, while the
        second core is not running. Once the initial arrays are made, we delegate that to the second core."""

        self.nvoices = nvoices
        self.notes_length = 96-33  # use this as the array offset per voice
        self.arr = array("I", [0] * nvoices * self.notes_length)  # one position per voice per note
        # coarse is the upper 8 bits, fine is the lower 8.
        self.pid = PidController(8192, 0, 0)  # used for all voices

    def get(self, voice, midinote):

        """Returns the composite coarse, fine voltage number to send to the DAC"""

        addr = voice * self.notes_length + midinote - 33  # offset of 33 because that's the lowest note on keyboard
        return self.arr[addr]  # split this apart on the receiving end to coarse, fine to avoid allocating a tuple

    def send_sample(self, voice, midinote):

        """use a frequency measurement to determine how big our error is and possibly correct it"""

        pass

    def setup_arrays(self):

        """For each voice, determine coarse and fine voltages for each note, and write them to the tuning array"""

        for x in range(self.nvoices):
            self.setup_array(x)
            print(f"set up tuning array for voice {x}")

    def optimize_arrays(self, voice=None):

        if not voice:  # default assumption is we are doing all voices
            for x in range(self.nvoices):
                for midinote in range(36, 96):
                    self.optimize(x, midinote)
                    print(f"Tuned voice {x} note {midinote}")
        else:
            pass  # tune just a single voice's array

    def setup_array(self, voice):

        fitter = self.fit_line(voice)
        start = voice * self.notes_length
        for x in range(self.notes_length):
            target_wavecount = fitter.getx(NOTE_WAVECOUNTS[x+33])
            self.arr[start + x] = target_wavecount  # initial rough values to optimize afterwards
            # misleading name, those are really voltages

        for x in self.arr:
            print(x >> 8, x & 255)


    def fit_line(self, voice):

        ADDRESS_MANAGER.put(voice)
        prepare_tune_latch()

        fitter = FitterFP(4)
        send_dac_value(5, 0)  # fine voltage = 0 for calibration

        for q in range(12, 255, 64):  # 4 steps across the whole voltage range
            send_dac_value(4, q)
            time.sleep(0.01)
            flush_pio()
            ema_reset()
            r = None
            while not r:
                r = get_sample_mean()
            fitter.add(q, fast_log2(r))

        fitter.fit_line()
        return fitter

    def optimize(self, voice, midinote):

        """Assuming the tuning array has been written first, use the PID to home in on the exact fine value, and
        choose a coarse, fine combination that gives leeway either side for fine to be increased/decreased."""

        ADDRESS_MANAGER.put(voice)
        prepare_tune_latch()
        self.pid.reset()

        send_dac_value(3, 127)  # PWM half to get good frequency measurement

        # initial setup of the process
        tnow = time.ticks_us()
        last_pid_time = time.ticks_us()
        convergence_possible = 0  # a counter for how many samples we got within the error tolerance. Past the threshold,
        # we consider the note tuned and move on.
        convergence_threshold = 5  # how many good samples before we consider the note stabilized and tuned
        converged = False  # condition to exit the loop, when we have recorded enough good measurements
        sample_count = 8  # how many samples do we aim to record for this note? More for higher freqs
        # todo - lower cnt for lower freqs, which take longer to record
        error_ema = 999  # smoothed error for measuring played note

        target_note = NOTE_WAVECOUNTS[midinote]  # converted to log2 freq units
        voltages = self.get(voice, midinote)
        coarse = voltages >> 8  # signals to send to the DAC
        fine = voltages & 255
        error = None

        send_dac_value(4, coarse)
        send_dac_value(5, fine)
        time.sleep(0.01)
        flush_pio()
        ema_reset()

        #print(f"Target note: {target_note}")

        while not converged:  # this could probably be while 1 now that we have an explicit break

            #print(error_ema)
            #if error:
                #print(error)
            #print(coarse)
            #print(fine)
            #print("---")

            tlast = tnow
            tnow = time.ticks_us()
            loop_time = time.ticks_diff(tnow, tlast)

            sample = None
            while not sample:  # we will ALWAYS wait for a sample
                sample = fast_log2(get_sample_mean(sample_count))

            print(sample, target_note)

            error = sample - target_note
            if error < 0:
                error = -1 * error  # absolute value is used to stop + and - errors cancelling each other out

            if error < ACCEPTABLE_ERROR:
                #print("converging...")
                convergence_possible += 1  # a counter
                error_ema = ((ERROR_EMA_ALPHA * error) >> 12) + (((4096 - ERROR_EMA_ALPHA) * error_ema) >> 12)
                print(error_ema)
                if error_ema < ACCEPTABLE_EMA and convergence_possible > convergence_threshold:
                    converged = True  # we have arrived at acceptable coarse, fine values and can bail out
                    break
                if error_ema < HIFREQ_EMA and target_note < 63000 and convergence_possible > convergence_threshold:
                    # more tolerance for hi freqs
                    converged = True  # we have arrived at acceptable coarse, fine values and can bail out
                    break
            else:
                convergence_possible = 0  # reset to start, need 4 continuous good measurements
                #print("convergence reset")

                # if we reach this part of the loop, we are still correcting


            if time.ticks_diff(tnow, last_pid_time) > MINIMUM_PID_INTERVAL:
                last_pid_time = tnow
                correction = self.pid.get_correction(sample - target_note)  # todo: tidy up so we use the error calc
                #print("+++")
                #print(correction)
                #print("+++")
                fine += correction
                #print("sample", sample)
                #print("tgt", target_note)
                #print("correxion", correction)

                # if fine has exceeded the range 0 to 255 we need to send a coarse adjustment instead, and then
                # send the remainder as the fine adjustment
                if 0 < fine < 255:
                    pass  # do nothing and just send fine as normal
                elif fine < 0:
                    fine *= -1
                    coarse -= (fine // 255) + 1
                    fine = 255 - (fine % 255)
                    send_dac_value(4, coarse)

                elif fine > 255:
                    coarse += fine // 255
                    fine = fine % 255
                    send_dac_value(4, coarse)

                send_dac_value(5, fine)

        addr = voice * self.notes_length + midinote - 33

        #self.arr[midinote - 33] = (coarse << 8) | fine
        self.arr[addr] = (coarse << 8) | fine
        #return (coarse << 8) | fine