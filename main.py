# ===== slow processor down to save battery power
if False:
    import machine
    machine.freq(80000000, min_freq=10000000)

# ===== connect to Wifi, not needed if using mqtt_as, but useful if running other tests
if False:
    import network, board
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

#import weather

if False:
    import wind, machine, time
    import uasyncio as asyncio
    loop = asyncio.get_event_loop()
    anemo_pin = machine.Pin(32, mode=machine.Pin.IN, pull=machine.Pin.PULL_UP)
    anemo_ctr = machine.Counter(0, 32)
    anemo_ctr.init(direction=machine.Counter.UP)
    print("ctr init {}".format(anemo_ctr.value()))
    print(anemo_ctr)
    for _ in range(5):
        time.sleep_ms(1000)
        print("ctr {}".format(anemo_ctr.value()))
    print(anemo_ctr)
    anemo = wind.Anemo(anemo_ctr, 2.5)
    async def mm():
        anemo.start(loop, gust_ms=1000)
        while True:
            await asyncio.sleep_ms(3000)
            w, g = anemo.read()
            print("wind: {} -- gust: {}".format(w, g))
    loop.run_until_complete(mm())

