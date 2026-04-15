from voice2 import Voice
from mydacs import DAC_MESSAGES
from omni import VOICE_PARAMS

CONTROL_FUNCTIONS = [-1] * 128
CONTROL_FUNCTIONS[73] = lambda v: set_base_parameter(1, v)
CONTROL_FUNCTIONS[75] = lambda v: set_filter_cutoff(6, v)
CONTROL_FUNCTIONS[79] = lambda v: set_base_parameter(7, v)
CONTROL_FUNCTIONS[72] = lambda v: set_base_parameter(3, v)
CONTROL_FUNCTIONS[80] = lambda v: set_base_parameter(0, v)

def set_base_parameter(dac_channel, value):

    #global DIRTY_PARAMS

    VOICE_PARAMS[dac_channel] = value
    #DIRTY_PARAMS |= 1 << (8 - dac_channel)  # bitmask is right to left, but array is left to right

    print(f"{dac_channel} set to {value}")
    #print(Voice.dirty_parameters)
    #print(VOICE_PARAMS)

def set_filter_cutoff(dac_channel, value):

    #global DIRTY_PARAMS

    VOICE_PARAMS[dac_channel] = 65535 - value  # filter is backwards: higher voltage = more open
    #DIRTY_PARAMS |= 1 << (8 - dac_channel)

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

        # TODO: no lol
        if channel == 74:  # a
            return
        if channel == 71:  # d
            return
        if channel == 76:  # s
            return
        if channel == 77:  # r
            return
        if channel == 93:  # env depth
            return
        if channel == 81:  # LFO  rate
            return
        if channel == 82:  # LFO depth
            return
        if channel == 83:  # LFO shape
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



