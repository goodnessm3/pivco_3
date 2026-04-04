from array import array


class FitterFP:
    """Fixed point fit optimized for MicroPython on RP2040 (8-bit fraction) vibe coded with Gemini"""

    def __init__(self, size=15, array_type="I"):
        self.size = size
        self.xs = array("I", [0] * size)
        self.ys = array(array_type, [0] * size)
        self.index = 0
        self.m = 0
        self.c = 0

    def add(self, x, y):
        # Store numbers raw! x (0-255), y (approx 0-65535).
        # This prevents the sums from overflowing 31-bit small ints.
        self.xs[self.index] = x
        self.ys[self.index] = y
        self.index = (self.index + 1) % self.size

    def fit_line(self):
        n = self.size
        sum_x = 0
        sum_y = 0
        sum_xx = 0
        sum_xy = 0

        for i in range(n):
            x = self.xs[i]
            y = self.ys[i]
            sum_x += x
            sum_y += y
            sum_xx += x * x
            sum_xy += x * y

        denom = n * sum_xx - sum_x * sum_x
        if denom == 0:
            return None

            # m will carry 8 bits of fractional precision (scale of 256)
        self.m = ((n * sum_xy - sum_x * sum_y) << 8) // denom

        # c will carry 8 bits of fractional precision to match m
        self.c = ((sum_y << 8) - self.m * sum_x) // n

    def getx(self, y):
        """
        Takes a raw integer frequency y.
        Returns a 16-bit packed integer x (upper 8 bits = coarse, lower 8 bits = fine).
        Upper 8 bits is the integer voltage to send to the coarse output. Then the fine is a fraction of 255 of
        the coarse range.
        """
        # (y << 8) - c has scale 2^8. We shift left by another 8 to get scale 2^16.
        # Dividing by m (scale 2^8) leaves us with a result of scale 2^8!
        return (((y << 8) - self.c) << 8) // self.m

    def gety(self, x_fp):
        """
        Takes a 16-bit packed integer x (where lower 8 bits are fractional/fine).
        Returns the raw integer frequency y.
        """
        # x_fp has scale 2^8, m has scale 2^8. Product has scale 2^16.
        # Shift down by 8 to scale back to raw integers.
        return ((self.m * x_fp) >> 8) + self.c