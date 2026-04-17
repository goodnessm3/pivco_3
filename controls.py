from voice2 import Voice
from mydacs import DAC_MESSAGES
from omni import VOICE_PARAMS
from ADSR3 import ADSRS
from LFO2 import LFOS
VOICES = []  # this will be replaced by a voice list passed from the main module
from settings import *

def configure_voice_list(ls):

    global VOICES

    VOICES = ls


def set_adr(param, value):

    offset = 0
    idx = SELECTED_PARAMETER
    # this will be read from the state of which parameter we selected from the param select knob
    for _ in range(4):
        ADSRS[idx + offset].set_rate(param, value)
        offset += 8  # need to update 4 ADSRs, one per voice


def set_sustain_level(value):

    idx = SELECTED_PARAMETER
    offset = 0
    for _ in range(4):
        ADSRS[idx + offset].sustain_level = value
        offset += 8  # need to update 4 ADSRs, one per voice

def set_base_parameter(dac_channel, value):

    VOICE_PARAMS[dac_channel] = value

def set_adsr_depth(value):

    offset = 0
    idx = SELECTED_PARAMETER
    parm = PARAMETER_NAMES[SELECTED_PARAMETER]
    print(f"setting depth of {parm}")
    # this will be read from the state of which parameter we selected from the param select knob
    for voice in range(VOICE_COUNT):
        ADSRS[idx + offset].depth = value  # todo - when 0, skip getting values from this ADSR
        if value > 0:
            VOICES[voice].active_adsrs |= 1 << idx  # tell the voice that it needs to query this ADSR in update()
            print(f"Voices will get updates from {parm} ASDR.")
        else:
            VOICES[voice].active_adsrs &= ~(1 << idx)  # no need to query this ADSR
            print(f"Voices will not update {parm} ASDR.")
        offset += 8  # need to update 4 ADSRs, one per voice

def set_lfo_rate(value):

    LFOS[SELECTED_PARAMETER].rate = value

def set_lfo_depth(value):

    LFOS[SELECTED_PARAMETER].depth = value

    parm = PARAMETER_NAMES[SELECTED_PARAMETER]

    for voice in range(VOICE_COUNT):
        if value > 0:
            VOICES[voice].active_lfos |= 1 << SELECTED_PARAMETER  # tell the voice that it needs to query
            print(f"Voices will get updates from {parm} LFO.")
        else:
            VOICES[voice].active_lfos &= ~(1 << SELECTED_PARAMETER)  # no need to query this
            print(f"Voices will not update {parm} LFO.")

def set_lfo_shape(value):

    LFOS[SELECTED_PARAMETER].shape = value
    shp = LFOS[SELECTED_PARAMETER].shape

    parm = PARAMETER_NAMES[SELECTED_PARAMETER]
    print(f"LFO for {parm} is {shp}")


def set_filter_cutoff(dac_channel, value):

    VOICE_PARAMS[dac_channel] = 65535 - value  # filter is backwards: higher voltage = more open

def parameter_select(value):

    global SELECTED_PARAMETER

    SELECTED_PARAMETER = (value // 4096) % 8
    print(PARAMETER_NAMES[SELECTED_PARAMETER])


adsr_parameter_mapping = {
    74: "a",
    71: "d",
    76: "s",
    77: "r",
    93: "depth"
}

lfo_parameter_mapping = {81: "rate", 82: "depth", 83: "shape"}

voice_parameter_mapping = {
    73: "suboctave",
    75: "cutoff",
    79: "resonance",
    72: "pwm",
    80: "external"
}

option_lists = {"shape":["SAW", "RAMP", "TRI", "SINE", "SHARK"],
                "invert": ["ON", "OFF"]
               }


CONTROL_FUNCTIONS = [-1] * 128

CONTROL_FUNCTIONS[19] = parameter_select  # doesn't need to be a lambda func because it just takes the knob value

CONTROL_FUNCTIONS[73] = lambda v: set_base_parameter(1, v)
CONTROL_FUNCTIONS[75] = lambda v: set_filter_cutoff(6, v)
CONTROL_FUNCTIONS[79] = lambda v: set_base_parameter(7, v)
CONTROL_FUNCTIONS[72] = lambda v: set_base_parameter(3, v)
CONTROL_FUNCTIONS[80] = lambda v: set_base_parameter(0, v)

CONTROL_FUNCTIONS[93] = set_adsr_depth

CONTROL_FUNCTIONS[74] = lambda v: set_adr(1, v)  # a
CONTROL_FUNCTIONS[71] = lambda v: set_adr(2, v)  # d
CONTROL_FUNCTIONS[77] = lambda v: set_adr(4, v)  # r
CONTROL_FUNCTIONS[76] = lambda v: set_sustain_level(v)  # r

CONTROL_FUNCTIONS[81] = set_lfo_rate
CONTROL_FUNCTIONS[82] = set_lfo_depth
CONTROL_FUNCTIONS[83] = set_lfo_shape

SELECTED_PARAMETER = 0  # this determines which LFO and ADSR we are modifying
PARAMETER_NAMES = ["EXT", "SUB", "VCA", "PWM", "COARSE", "FINE", "CUTOFF", "RES"]


class Controls:

    def __init__(self):

        pass

    def process_control_signal(self, control_message):

        # these won't be set if we are changing the selected ADSR/LFO, still need to update
        # the display with the identity of the changed object though

        channel = control_message >> 8
        value = (control_message & 255) << 8  # scale up to use 16-bit internally

        dac_channel = -1  # in the if-elif block below we set this based on what control was manipulated

        if channel < 128:  # check if it's a hardware parameter slider, probably the most common operation
            func = CONTROL_FUNCTIONS[channel]  # index in list corresponds to dac channel
            if func != -1:
                func(value)  # evaluate the lambda function with the value from the control
                # catch that we are changing a parameter
                #Voice.parameters[dac_channel] = value  # set the class-level attribute to affect all voices
                #Voice.dirty_parameters |= 1 << dac_channel
                return

        print(channel, value)  # for debugging and catching new controls
        return




        if channel == 17:  # param select knob,
            return  # TODO - fill in later
        elif channel == 85:  # generic entry for any value
            return  # TODO - fill in later
        elif channel == 23:
            if value > 127:
                print("tap button - use for graceful shutdown")  # TODO
                pass
                #self.shutdown_handler()  # run the shutdown function
            return



