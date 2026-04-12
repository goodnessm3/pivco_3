from settings import *  # definitions of all constants used in the code
from pin_assignments import *
from rp2 import PIO, asm_pio
import machine
import rp2
from fastlog2 import fast_log2
from array import array

@asm_pio(autopush=True, fifo_join=PIO.JOIN_RX)  # RX FIFO will be pushed to when we have 2 16-bit values
def clocker():
    # pull(noblock)      # Load max counter value to OSR
    mov(x, invert(null))  # Reset Counter
    wrap_target()
    label("count")
    jmp(pin, "write")  # Check sync pin
    jmp(x_dec, "count")
    label("write")
    # mov(isr, x)        # Capture count
    in_(x, 16)
    # push(noblock)
    mov(x, invert(null))  # Reset Counter immediately
    wait(0, pin, 0)  # Wait for sync low
    wrap()


# we want to use in rather than mov to put fewer bytes into the ISR at a time.

@asm_pio(sideset_init=PIO.OUT_LOW)
def edge_watcher():
    wrap_target()
    wait(1, pin, 0)
    nop().side(1)[3]  # Pulse High for 3 cycles
    nop().side(0)
    wait(0, pin, 0)
    nop().side(1)[3]  # Pulse High for 3 cycles
    nop().side(0)
    wrap()


# Pin Setup
gppin = machine.Pin(P_TUNE_INPUT, machine.Pin.IN, machine.Pin.PULL_UP)
sidepin = machine.Pin(P_PIN_SYNC, machine.Pin.OUT)
sidepin.value(0)

sm_clocker = rp2.StateMachine(0, clocker, freq=SM_FREQ, jmp_pin=sidepin)
sm_edger = rp2.StateMachine(1, edge_watcher, freq=SM_FREQ, in_base=gppin, sideset_base=sidepin)

sm_clocker.active(1)
sm_edger.active(1)

EMA = 0
LAST_VALID = 0  # use to filter anomalies that might come from pausing due to gc
ERROR_TOLERANCE = INITIAL_ERROR_TOLERANCE  # to be refined once the tuning is done
EXPECTED = 0
DISCARD_COUNTER = 0  # when we reset the EMA, throw away the first 3 samples from the PIO which will always be wrong

MEANS = array("I", [0] * 32)
MEANS_FILTERED = array("I", [0] * 32)

def get_sample(max_samples=8, alpha=None):

    global EMA
    global LAST_VALID
    global DISCARD_COUNTER

    if not alpha:  # TODO - probably not needed any more
        alpha = EMA_ALPHA
    else:
        alpha = alpha

    cnt = 0
    first = True

    fifosize = sm_clocker.rx_fifo()
    while fifosize > 0:
        if fifosize == 8:  # the FIFO filled up completely and we need to discard the first measurement
            _ = sm_clocker.get()
        #print("inside fifo getting")
        d = sm_clocker.get()

        fifosize = sm_clocker.rx_fifo()

        DISCARD_COUNTER += 1
        if DISCARD_COUNTER < 4:
            continue  # when we reset the EMA, throw away the first 3 samples from the PIO

        """
        if first:
            # have to throw away first measurement, it might be wonky if the sm stalled
            first = False
            continue
        """

        # we were decrementing the counter, so need to subtract from max val to get elapsed clock cycles
        x = MAXX - (d >> 16)
        y = MAXX - (d & 0xFFFF)  # splitting 32-bit number into 2 16-bit numbers
        measurement = x + y  # this func just measures the wave cycle time, we are not interested in hi and lo parts

        if EMA == 0:
            EMA = measurement  # don't "shock" the EMA with a zero starting value
        else:
            delta = measurement - LAST_VALID
            if delta < 0:
                delta = -delta

            #print(delta)
            #print(LAST_VALID)

            if delta < ERROR_TOLERANCE:
                EMA = ((alpha * measurement) >> 12) + (((4096 - alpha) * EMA) >> 12)

        LAST_VALID = measurement

        cnt += 1
        if cnt > max_samples:
            #print(EMA)
            return fast_log2(EMA)
    #print("from outer loop", EMA)
    if cnt > 0:
        return fast_log2(EMA)
    ############################
    #return EXPECTED  # potential for really stupid bugs but we always must return something
    ############################



def get_sample_mean(samples=8):

    global MEANS
    global MEANS_FILTERED

    for x in range(samples):
        MEANS_FILTERED[x] = 0  #re-zero array for next time

    if samples > 32:
        samples = 32  # max size of the buffer where we store these
    idx = 0
    smp = None

    while 1:
        while not smp:
            smp = sm_clocker.get()
        x = MAXX - (smp >> 16)
        y = MAXX - (smp & 0xFFFF)  # splitting 32-bit number into 2 16-bit numbers
        measurement = x + y  # this func just measures the wave cycle time, we are not interested in hi and lo parts
        MEANS[idx] = measurement
        idx += 1
        if idx == samples:
            break
        smp = None

    # now we have gathered the requested number of measurements, calculate mean and discard anomalies
    # take the median
    m = 0
    idx = 1  # don't use zero and wrap the array, because sometimes the end of the array will be unfilled
    while idx < samples:
        d = MEANS[idx] - MEANS[idx-1]
        m += d
        idx += 1

    # now go thru the array again and throw out anomalies
    good_samples = 0
    idx = 1
    while idx < samples:
        d = MEANS[idx] - MEANS[idx-1]

        if d > ERROR_TOLERANCE:
            #print("threw out", MEANS[idx], MEANS[idx-1])
            idx += 2
            continue  # delta is too large, don't include this pair of measurements
        else:
            MEANS_FILTERED[good_samples] = MEANS[idx-1]
            MEANS_FILTERED[good_samples+1] = MEANS[idx]
            good_samples += 2
            idx += 2

    #print(MEANS)
    #print(MEANS_FILTERED)
    #print("m", m)
    #print(samples)
    #print("tolerance", tolerance)

    # todo: make better with power of 2 samples and bit shift instead of division

    return sum(MEANS_FILTERED) // good_samples




def ema_reset(expected_value=0):

    global EMA
    global LAST_VALID
    global EXPECTED
    global DISCARD_COUNTER

    EMA = 0
    LAST_VALID = 0
    EXPECTED = expected_value
    DISCARD_COUNTER = 0

def freq_counter_cleanup():
    sm_clocker.active(0)
    sm_edger.active(0)
    print("frequency counter stopped.")

def flush_pio():

    """Empty the FIFO because we don't want our new measurement contaminated with old values. Most useful when
        we changed frequency and want to only measure the new frequency"""

    while sm_clocker.rx_fifo() > 0:
        sm_clocker.get()



def get_sample_mean_float(samples=8):

    global MEANS
    global MEANS_FILTERED

    for x in range(samples):
        MEANS_FILTERED[x] = 0  #re-zero array for next time

    if samples > 32:
        samples = 32  # max size of the buffer where we store these
    idx = 0
    smp = None

    while 1:
        while not smp:
            smp = sm_clocker.get()
        x = MAXX - (smp >> 16)
        y = MAXX - (smp & 0xFFFF)  # splitting 32-bit number into 2 16-bit numbers
        measurement = x + y  # this func just measures the wave cycle time, we are not interested in hi and lo parts
        MEANS[idx] = measurement
        idx += 1
        if idx == samples:
            break
        smp = None

    # now we have gathered the requested number of measurements, calculate mean and discard anomalies
    # take the median
    m = 0
    idx = 1  # don't use zero and wrap the array, because sometimes the end of the array will be unfilled
    while idx < samples:
        d = MEANS[idx] - MEANS[idx-1]
        m += d
        idx += 1

    # now go thru the array again and throw out anomalies
    good_samples = 0
    idx = 1
    while idx < samples:
        d = MEANS[idx] - MEANS[idx-1]

        if d > ERROR_TOLERANCE:
            #print("threw out", MEANS[idx], MEANS[idx-1])
            idx += 2
            continue  # delta is too large, don't include this pair of measurements
        else:
            MEANS_FILTERED[good_samples] = MEANS[idx-1]
            MEANS_FILTERED[good_samples+1] = MEANS[idx]
            good_samples += 2
            idx += 2

    #print(MEANS)
    #print(MEANS_FILTERED)
    #print("m", m)
    #print(samples)
    #print("tolerance", tolerance)

    return sum(MEANS_FILTERED) / float(good_samples)
