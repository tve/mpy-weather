import wind, machine, time
import uasyncio as asyncio
print("Starting anemo test")

loop = asyncio.get_event_loop()
anemo_pin = machine.Pin(21, mode=machine.Pin.IN, pull=machine.Pin.PULL_UP)
anemo_ctr = machine.Counter(21)
if False:
    print("ctr init {}".format(anemo_ctr.value()))
    print(anemo_ctr)
    for _ in range(20):
        time.sleep_ms(1000)
        print("ctr {}".format(anemo_ctr.value()))
    print(anemo_ctr)

if True:
    anemo = wind.Anemo(anemo_ctr, 2.5)
    async def mm():
        anemo.start(loop, gust_ms=1000)
        while True:
            await asyncio.sleep_ms(3000)
            w, g = anemo.read()
            print("wind: {} -- gust: {}".format(w, g))
    loop.run_until_complete(mm())

