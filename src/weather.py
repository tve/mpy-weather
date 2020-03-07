import board, machine, time, aqi
from counter import Counter
from mqtt_as import MQTTClient, config
from config import wifi_led, blue_led
import uasyncio as asyncio
import ujson as json

print("\n===== esp32 weather `{}` starting at {} =====\n".format(board.location, time.time()))

TOPIC = 'esp32/weather/' + board.location

QUERY_INTERVAL = const(60*1000) # milliseconds

# ===== pin configuration

if board.kind == "lolin-d32":
    scl, sda = 23, 22
    pm_rx = 16
    anemo_pin = 17
elif board.kind == "huzzah32":
    scl, sda = 23, 22
    pm_rx = 39
    anemo_pin = 32
    vane_pin = 14
    rain_pin = 33
else:
    raise("Unknown board kind: " + board.kind)

# ===== init devices

got_bme680 = True
got_si7021 = True
got_sht31 = True
got_pmsx003 = True
got_anemo = False
got_vane = True
got_rain = True

# start fan blowing on sensors
#fan = machine.Pin(16, machine.Pin.OUT)
#fan(1)

loop = asyncio.get_event_loop()
outages = 0

import i2c
scl_pin = machine.Pin(scl)
sda_pin = machine.Pin(sda)
i2c_dev = i2c.I2CAdapter(scl=scl_pin, sda=sda_pin)

import bme680
try:
    b6 = bme680.BME680(i2c_device=i2c_dev)
    b6.set_gas_heater_temperature(320)
    b6.set_gas_heater_duration(100)
    print("Found BME680")
except Exception as e:
    got_bme680 = False
    print("No BME680 found:", e)

from si7021 import Si7021
try:
    si7 = Si7021(addr=0x40, scl=scl, sda=sda)
    si7.convert()
    print("Found Si7021")
except Exception as e:
    got_si7021 = False
    print("No Si7021 found:", e)

from sht31 import SHT31
try:
    sh3 = SHT31(machine.I2C(scl=scl_pin, sda=sda_pin, freq=100000))
    sh3.convert()
    print("Found SHT31")
except Exception as e:
    got_sht31 = False
    print("No SHT31 found:", e)

# init PMSx003 PM sensor
import pms_x003
try:
    p3 = pms_x003.PMSx003(tx=-1, rx=pm_rx)
    print("Found PMSx003")
except Exception as e:
    got_pmsx003 = False
    print("No PMSx003 found:", e)

# init anemometer
import wind
try:
    machine.Pin(anemo_pin, mode=machine.Pin.IN, pull=machine.Pin.PULL_UP)
    anemo_ctr = Counter(anemo_pin)
    anemo = wind.Anemo(anemo_ctr, 2.5) # 2.5 mph per Hz
except Exception as e:
    print("Anemometer failed to init:", e)

# init wind vane
try:
    vane = wind.Vane(vane_pin, 0, 3.3, 0)
except Exception as e:
    got_vane = False
    print("Wind vane failed to init:", e)

# init rain gauge

# ===== asyncio and mqtt callback handlers

# pulse blue LED
async def pulse():
    blue_led(True)
    await asyncio.sleep_ms(100)
    blue_led(False)

# handle the arrival of an MQTT message
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

# ===== read queryable sensors

wdt_query_sensors = 0

# PM2.5 sensor averaging
pm_sum = [0, 0]
pm_cnt = 0

async def query_sensors(client):
    t0 = time.ticks_ms()
    while True:
        data = {}
        gas, pm25 = None, None
        # convert the bme680
        if got_bme680:
            await asyncio.sleep_ms(b6.convert())
            while not b6.ready():
                await asyncio.sleep_ms(10)
            (t, h, p, gas) = b6.read_data()
            print("BME680: T={:.1f}°F H={:.0f}% P={:.3f}mBar G={:.3f}kΩ".format(t*1.8+32, h, p, gas/1000))
            (data['t_bme680'], data['h_bme680'], data['p_bme680'], data['g_bme680') += (t, h, p/1000, gas)
        # read the si7021
        if got_si7021:
            await asyncio.sleep_ms(si7.convert()+2)
            (t, h) = si7.read_temp_humi()
            print("Si7021: T={:.1f}°F H={:.0f}%".format(t*1.8+32, h))
            (data['t_si7021'], data['h_si7021']) = (t, h)
        # read sht31
        if got_sht31:
            await asyncio.sleep_ms(sh3.convert()+2)
            (t, h) = sh3.read_temp_humi()
            print("SHT31 : T={:.1f}°F H={:.0f}%".format(t*1.8+32, h))
            (data['t_sht31'], data['h_sht31']) = (t, h)
        # read wind
        if got_anemo:
            (w, g) = anemo.read()
            print("Wind  : {:.0fmph} gust:{:.0fmph}".format(w, g), end='')
            (data['wind'], data['gust']) = (w, g)
            if got_vane:
                d = vane.read()
                print(" dir={.0f}°")
                data['wdir'] = d
            else:
                print()
        # read rain gauge

        # insert averaged dust data
        global pm_cnt, pm_sum
        if pm_cnt > 0:
            d = [v/pm_cnt for v in pm_sum]
            pm25 = d[0]
            data['pm25'] = pm25
            pm_sum = [0 for _ in pm_sum]
            pm_cnt = 0

        # AQI conversions
        if gas is not None:
            data['aqi_tvoc'] = aqi.tvoc_bme680(gas)
        if pm25 is not None:
            data['aqi_pm25'] = aqi.pm25(pm25)

        # publish data
        if any(d is not None for d in data):
            print("pub:", data)
            await client.publish(TOPIC+"/sensors", json.dumps(data), qos = 1)

        # keep the dog sleeping
        global wdt_query_sensors
        wdt_query_sensors = time.ticks_ms()

        # sleep
        t1 = time.ticks_ms()
        dt = time.ticks_diff(t1, t0)
        if dt < QUERY_INTERVAL:
            await asyncio.sleep_ms(QUERY_INTERVAL - dt)
            t0 = time.ticks_add(t0, QUERY_INTERVAL)
        elif dt < QUERY_INTERVAL * 3 / 2:
            t0 = time.ticks_add(t0, QUERY_INTERVAL)
        else:
            t0 = time.ticks_ms()

# ===== read uart sensors that send data when they please

wdt_poll_uarts = 0

async def poll_uarts(client):
    global pm_sum, pm_cnt
    while True:
        # read the PMSA003
        if got_pmsx003:
            pm2_5 = p3.read()
            while pm2_5 is not None:
                for i, v in enumerate(pm2_5): pm_sum[i] += v
                pm_cnt += 1
                print("PMSx003: D={:d}µg/m³ X={:d}".format(pm2_5[0], pm2_5[1]))
                pm2_5 = p3.read()
        # sleep
        global wdt_poll_uarts
        wdt_poll_uarts = time.ticks_ms()
        await asyncio.sleep_ms(500)

# ===== main loop

async def main(client):
    # get an initial connection
    blue_led(True)
    try:
        await client.connect()
    except OSError:
        print('Connection failed')
        return
    # TODO: wait for time sync
    # launch tasks
    loop.create_task(query_sensors(client))
    loop.create_task(poll_uarts(client))
    # play watchdog
    global wdt_query_sensors, wdt_poll_uarts
    wdt_query_sensors = time.ticks_ms()
    wdt_poll_uarts = time.ticks_ms()
    while True:
        now = time.ticks_ms()
        age = max(
            time.ticks_diff(now, wdt_query_sensors),
            time.ticks_diff(now, wdt_poll_uarts),
        )
        if age > 10*60*1000:
            machine.reset()
        await asyncio.sleep(33)

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
