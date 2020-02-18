# This example requires the micropython_dotstar library
# https://github.com/mattytrentini/micropython-dotstar

# ===== slow processor down to save battery power
if False:
    import machine
    machine.freq(80000000, min_freq=10000000)

# ===== connect to Wifi, not needed if using mqtt_as
if False:
    import network
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(board.wifi_ssid, board.wifi_pass)
    print('Waiting on Wifi in boot.py...')
    while not wlan.isconnected():
        pass
    print('Connected!')

# ===== set-up trigger output pin for debugging purposes
#from machine import Pin
#trig = Pin(12, Pin.OUT)
#trig(0)

import weather

