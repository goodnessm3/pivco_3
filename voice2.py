from array import array
from ADSR3 import ADSRS
from LFO2 import LFOS
from filtertable import FILTER_CVS
from mydacs import DAC_MESSAGES
from omni import VOICE_PARAMS


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
        self.active_adsrs = 4  # this is a bitmask that tells us which ADSRs to query. Default just to VCA.
        self.active_lfos = 0

        #for x in range(8):
            #self.adsrs.append(LinearADSR())
        self.adsrs = ADSRS[address * 8: address * 8 + 8]  # todo - memoryview?????
        self.lfos = LFOS

        #print(self.adsrs)

        self.base_values = array("H", [0] * 8)  # class-level parameters set by hardware sliders. Add our modulations
        # e.g. ADSRs and per-voice LFOs, to these variables

        self.key_counter = 0  # rather than true or false we need to increment/decrement a counter for "key rollover"


    def key_down(self):

        for x in self.adsrs:
            x.gate(True)
        self.key_counter += 1

    def key_up(self):

        self.key_counter -= 1
        if self.key_counter == 0:  # need this otherwise an old key up event will un-gate a newer note
            for x in self.adsrs:
                x.gate(False)

    def update(self):

        addr = self.address
        todo_adsr = self.active_adsrs
        todo_lfo = self.active_lfos
        # todo_params = DIRTY_PARAMS  # a static parameter got changed by a slider

        chan = 0

        #print(VOICE_PARAMS)
        #print(todo_params)

        #while todo_adsr or todo_lfo or todo_params:
        while chan < 8:
            if not chan == 4 or chan == 5:  # don't overwrite VCO control voltage
                modulation = VOICE_PARAMS[chan]

            if todo_adsr & 1:
                val = self.adsrs[chan].get()
                modulation += val

            if todo_lfo & 1:
                val = self.lfos[chan].get(self.address)  # LFOs track the caller to do a unique phase offset
                modulation += val

            if not chan == 4 or chan == 5:  # don't overwrite VCO control voltage
                # scale down from 16-bit internal calcs to 8-bit DAC resolution
                DAC_MESSAGES.set(addr, chan, modulation >> 8)
            todo_adsr >>= 1
            todo_lfo >>= 1
            #todo_params >>= 1
            chan += 1

            # TODO: make it so VCO CV is applied via the same mechanism





