import wind, machine, time
import uasyncio as asyncio
print("Starting vane test")

loop = asyncio.get_event_loop()
vane = wind.Vane(33, 1900, 61240, 0)

print(vane._avg(vane._avg(20, 40), 40))
print(vane._avg(vane._avg(10, 300), 300))
print(vane._avg(vane._avg(350, 60), 60))

async def mm():
    vane.start(loop)
    while True:
        d = vane.read()
        (vmin, vmax) = vane.min_max()
        print("dir: {} ({}..{})".format(d, vmin, vmax))
        await asyncio.sleep_ms(5000)
loop.run_until_complete(mm())

