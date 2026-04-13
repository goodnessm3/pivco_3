from array import array
from ADSR3 import LinearADSR
from filtertable import FILTER_CVS
from mydacs import DAC_MESSAGES

class GlobalMods:

    def __init__(self):

        self.parameters = array("H", [0] * 8)  # baseline quantities to which we add modulations

    def get(self, channel):

        return self.parameters[channel]

GLOBALMODS = GlobalMods()


class Voice:



    def __init__(self, address, cutoff_freq_tracking=True):

        """
        DAC channels
        0 - external signal
        1 - suboctave
        2 - VCA
        3 - PWM
        4 - coarse VCO
        5 - fine VCO
        6 - filter cutoff
        7 - filter resonance

        """

        self.address = address
        self.cutoff_freq_tracking = cutoff_freq_tracking  # TODO: configurable later
        self.adsrs = []
        self.active_adsrs = 4  # this is a bitmask that tells us which ADSRs to query. Default just to VCA.
        self.active_lfos = 0


        for x in range(8):
            self.adsrs.append(LinearADSR())

        self.base_values = array("H", [0] * 8)  # class-level parameters set by hardware sliders. Add our modulations
        # e.g. ADSRs and per-voice LFOs, to these variables


    def key_down(self):

        for x in self.adsrs:
            x.gate(True)

    def key_up(self):

        for x in self.adsrs:
            x.gate(False)

    def update(self):

        addr = self.address
        todo_adsr = self.active_adsrs
        todo_lfo = self.active_lfos
        #todo_adsr = 255  # todo temporary! need a better way to set global stuff
        todo_lfo = 0
        chan = 0
        while todo_adsr or todo_lfo:
            modulation = GLOBALMODS.get(chan)
            if chan == 6:
                print("from in voice class, co =", modulation)
            if todo_adsr & 1:
                val = self.adsrs[chan].get()
                modulation += val
                DAC_MESSAGES.set(addr, chan, modulation >> 8)
                # scale down from 16-bit internal calcs to 8-bit DAC resolution
            # todo: LFO mods
            todo_adsr >>= 1
            chan += 1



