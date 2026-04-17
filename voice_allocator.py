from array import array
from custom_fifo import CustomFIFO

class VoiceAllocator:

    def __init__(self, nvoices):

        self.arr = array("B", [99] * nvoices)
        self.nvoices = nvoices

    def next(self):

        mx = 0
        idx = 0
        arr = self.arr
        found_index = 0

        while idx < self.nvoices:
            if arr[idx] > mx:
                mx = arr[idx]
                found_index = idx
            idx += 1

        return found_index  # the least recently played voice

    def key_down(self, v):

        arr = self.arr
        arr[v] = 0

        for idx in range(self.nvoices):
            arr[idx] += 1

    def key_up(self, v):

        self.arr[v] = 99
