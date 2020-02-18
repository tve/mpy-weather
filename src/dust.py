import board, machine
from mqtt_as import MQTTClient, config
from config import wifi_led, blue_led
import uasyncio as asyncio
import ujson as json

TOPIC = 'esp32/weather/' + board.location

loop = asyncio.get_event_loop()
outages = 0

# init PMSx003 PM sensor
import pms_x003
p3 = pms_x003.PMSx003(tx=34, rx=39)

# pulse blue LED
async def pulse():
    blue_led(True)
    await asyncio.sleep_ms(100)
    blue_led(False)

# handle the arrival of a message
def sub_cb(topic, msg, retained):
    print((topic, msg))
    loop.create_task(pulse())

async def wifi_cb(state):
    global outages
    wifi_led(not state)  # Light LED when WiFi down
    if state:
        print('WiFi connected')
    else:
        outages += 1
        print('WiFi or broker is down')

async def conn_cb(client):
    print('MQTT connected')
    #await client.subscribe(TOPIC, 1)

async def main(client):
    blue_led(True)
    try:
        await client.connect()
    except OSError:
        print('Connection failed')
        return
    while True:
        data = []
        for i in range(8):
            data.append(None)

        # read the PMSA003
        pm2_5 = p3.read()
        if pm2_5 != None:
            print("PMSx003: D={:f}µg/m³ X={:d}".format(pm2_5[0], pm2_5[1]))

        #data += [t, h]
        ## publish data
        #print("pub:", data)
        #await client.publish(TOPIC+"/sensors", json.dumps(data), qos = 1)

        #await asyncio.sleep(1)

# Define configuration
#config['subs_cb'] = sub_cb
config['wifi_coro'] = wifi_cb
config['connect_coro'] = conn_cb
config['keepalive'] = 120

# power config
#machine.freq(80000000, min_freq=10000000)
#config['listen_interval']=5

# Set up client. Enable optional debug statements.
#MQTTClient.DEBUG = True
client = MQTTClient(config)

#import uasyncio, logging
#logging.basicConfig(level=logging.DEBUG)
#uasyncio.set_debug(True)

print("Starting loop...")
try:
    loop.run_until_complete(main(client))
finally:  # Prevent LmacRxBlk:1 errors.
    client.close()
    blue_led(True)
