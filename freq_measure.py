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
    in_(x, 32)
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


def get_sample_mean(samples=8):

    global MEANS
    global MEANS_FILTERED

    for x in range(samples):
        MEANS_FILTERED[x] = 0  #re-zero array for next time

    if samples > 32:
        samples = 32  # max size of the buffer where we store these
    idx = 0
    #x = None
    #y = None

    while 1:

        x = None
        y = None

        while not x:
            x = sm_clocker.get()
        while not y:
            y = sm_clocker.get()
        x = MAXX - x
        y = MAXX - y

        measurement = x + y  # this func just measures the wave cycle time, we are not interested in hi and lo parts
        MEANS[idx] = measurement
        idx += 1
        if idx == samples:
            break

    # now we have gathered the requested number of measurements, calculate mean and discard anomalies
    # take the median
    m = 0
    idx = 1  # don't use zero and wrap the array, because sometimes the end of the array will be unfilled
    while idx < samples:
        d = MEANS[idx] - MEANS[idx-1]
        m += d
        idx += 1

    # now go thru the array again and throw out anomalies

    #print(MEANS)

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

    #print(MEANS_FILTERED)

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




