from voice2 import GLOBALMODS
from mydacs import DAC_MESSAGES


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
    80: "external"  # CHECK!! this is probably for the breadboard version but NOT the PCB version
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
        value = control_message & 255

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
        elif channel == 75:  # cutoff
            GLOBALMODS.parameters[6] = value
            print("cutoff set to", value)
            DAC_MESSAGES.set(0, 6, value)