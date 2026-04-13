import time
from array import array

class LinearADSR:

    def __init__(self):

        self.max_level = 65535
        self.sustain_level = 20000

        self.rates = array("i", [0] * 5)  # how much we should increment/decrement the bucket per millisecond

        self.set_rate(1, 300)  # a
        self.set_rate(2, 1000)  # d
        self.set_rate(4, 450)  # r

        self.phase = 0  # 0 = quiescent, 1 = atk, 2, dky, 3 = sus, 4 = rel. These are used as array indices
        self.last_called = time.ticks_ms()
        self.bucket = 0

    def set_rate(self, rate_index, time):

        """a = 1, d = 2, r = 3. Time = the length of the phase in milliseconds from max to min"""

        """These numbers specify the gradient of each phase, i.e. how much the bucket in/de-creases over 1 millisecond"""

        val = 65535 // time
        if rate_index == 2 or rate_index == 4:  # decay and release are negative rates
            val = -1 * val
        self.rates[rate_index] = val

    def gate(self, status):

        if status:
            self.phase = 1
        else:
            self.phase = 4  # releasing

    def get(self):

        phase = self.phase
        if phase == 0:
            return 0  # not doing anything

        tdelta = time.ticks_diff(time.ticks_ms(), self.last_called)
        self.last_called = time.ticks_ms()

        self.bucket += self.rates[phase] * tdelta  # the rate of sustain is always 0 so doesn't change the bucket

        if self.bucket > self.max_level:
            self.bucket = self.max_level
            self.phase = 2  # move to decaying
        if self.bucket < self.sustain_level and phase == 2:
            self.bucket = self.sustain_level
            self.phase = 3
        if self.bucket < 0:
            self.bucket = 0
            self.phase = 0

        return self.bucket