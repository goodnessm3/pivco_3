from array import array

VOICE_COUNT = 2
SM_FREQ = 100_000_000
MAXX = 2**32-1  # highest number the frequency counter state machines can count down from
EMA_ALPHA = 2048  # 0 to 4096, this is for the EMA of the frequency measurement
INITIAL_ERROR_TOLERANCE = 16000 # how many wave count deviation before we consider a reading anomalous and reject it
# this experimentally determined value is used for the initial tuning, then we refine it once the tuning is done
MINIMUM_PID_INTERVAL = 3000  # we must wait at least this many microseconds between sending corrections from the PID
ERROR_EMA_ALPHA = 2048  # smoothing of the frequency samples that we collect
ACCEPTABLE_ERROR = 400  # the margin within which we increment the convergence counter
ACCEPTABLE_EMA = 5
HIFREQ_EMA = 10

