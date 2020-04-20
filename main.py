# ===== slow processor down to save battery power
if False:
    import machine
    machine.freq(80000000, min_freq=10000000)

# ===== set-up trigger output pin for debugging purposes
#from machine import Pin
#trig = Pin(12, Pin.OUT)
#trig(0)

import weather
weather.doit()
