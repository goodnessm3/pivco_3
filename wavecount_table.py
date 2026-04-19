from array import array
from fastlog2 import fast_log2
from settings import SM_FREQ

# lowest note on keyboard = 36
# highest note = 96

A1 = 55.00
NOTES = [0.0] * 133  # unused very low notes
NOTE_WAVECOUNTS = array("I", [0] * 133)

# going from A1 as it's the lowest integer number
# 96 is the highest MIDI note on the keyboard
for x in range(97):
    freq = round(A1 * 2**(x/12.0),2)
    NOTES[x + 33] = freq  # TODO: this is for diagnostic purposes but not control purposes
    NOTE_WAVECOUNTS[x + 33] = fast_log2(int(SM_FREQ//freq//2))  # TODO - can we clean this maths up?
    # generates a list where the item at the index of a MIDI note is the
    # wavecount of that note, that is, how many PIO clock cycles does it take to complete a high + low wave segment
    # so about 54000 for the lowest note, and 180 for the highest - the PIO frequency is chosen so that we use
    # most of the range of a 16-bit counter across the entire range of notes
    # this wavecounts table is used to define the set point of the autotuning PID.



class VoltageArrays:

    """Manages the storage and retrieval of what voltages were last optimized for a given note. Lets us be slightly
    more accurate than using the tuning curve every time, which will gradually drift away from being accurate."""

    def __init__(self):

        self.COARSE_VOLTAGES = array("B", [0] * 4 * 62)  # store a voltage for any of 4 voices and 62 notes.
        self.FINE_VOLTAGES = array("B", [0] * 4 * 62)

    def set(self, voiceno, midinote, coarse, fine):

        addr = voiceno * 62 + midinote -33  # offset of 33 is because that's the lowest note on the keyboard controller
        self.COARSE_VOLTAGES[addr] = coarse
        self.FINE_VOLTAGES[addr] = fine

    def get(self, voiceno, midinote):

        addr = voiceno * 62 + midinote -33
        return self.COARSE_VOLTAGES[addr], self.FINE_VOLTAGES[addr]

