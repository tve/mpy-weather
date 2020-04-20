import board, machine, time, aqi, logging
from counter import Counter
from ssd1306 import SSD1306_I2C
import uasyncio as asyncio
import ujson as json
from __main__ import gc_collect
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

TOPIC = board.mqtt_config["user"]

QUERY_INTERVAL = const(60*1000) # milliseconds

# ===== pin configuration, see also Projects/kicad/esp32-weather/README.md

if board.kind == "lolin-d32":
    scl0, sda0 = 23, 22   # bme680, si7021, sht31
    scl1, sda1 = 18,  4   # oled
    scl2, sda2 = 13, 12   # expansion
    pm_tx, pm_rx = 25, 26 # pmsa003
    anemo_pin = 39        # anemometer pulse
    vane_pin  = 36        # wind vane analog
    rain_pin  = 34        # rain pulse
    pow_3v3 = 32          # active-low power for anemo/vane/rain/pmsa003
else:
    raise("Unknown board kind: " + board.kind)

# ===== init devices

scl1_pin = machine.Pin(scl1)
sda1_pin = machine.Pin(sda1)
display = SSD1306_I2C(128, 64, machine.I2C(scl=scl1_pin, sda=sda1_pin, freq=1000000))
display.fill(1)
display.fill_rect(10, 10, 108, 44, 0)
display.text("WCC Weather", 20, 20, 1)
display.show()

got_bme680 = True
got_si7021 = True
got_sht31 = True
got_pmsx003 = True
got_anemo = False
got_vane = True
got_rain = True

# start power for anemo, vane, etc.
pow_3v3_pin = machine.Pin(pow_3v3, machine.Pin.OUT)
pow_3v3_pin(0)

scl0_pin = machine.Pin(scl0)
sda0_pin = machine.Pin(sda0)
i2c0_dev = machine.I2C(scl=scl0_pin, sda=sda0_pin, freq=100000)

import bme680
try:
    b6 = bme680.BME680(i2c0_dev)
    b6.set_gas_heater_temperature(320)
    b6.set_gas_heater_duration(100)
    log.info("Found BME680")
except Exception as e:
    got_bme680 = False
    log.warning("No BME680 found: %s", e)
gc_collect()

from si7021 import Si7021
try:
    si7 = Si7021(i2c0_dev)
    si7.convert()
    log.info("Found Si7021")
except Exception as e:
    got_si7021 = False
    log.warning("No Si7021 found: %s", e)
gc_collect()

from sht31 import SHT31
try:
    sh3 = SHT31(i2c0_dev)
    sh3.convert()
    log.info("Found SHT31")
except Exception as e:
    got_sht31 = False
    log.warning("No SHT31 found: %s", e)
gc_collect()

# init PMSx003 PM sensor
import pms_x003
try:
    p3 = pms_x003.PMSx003(tx=pm_tx, rx=pm_rx)
    log.info("Found PMSx003")
except Exception as e:
    got_pmsx003 = False
    log.warning("No PMSx003 found: %s", e)
gc_collect()

# init anemometer
import wind
try:
    # configure pin with pull-up
    machine.Pin(anemo_pin, mode=machine.Pin.IN, pull=machine.Pin.PULL_UP)
    anemo_ctr = Counter(anemo_pin)
    anemo = wind.Anemo(anemo_ctr, 2.5) # 2.5 mph per Hz
except Exception as e:
    log.warning("Anemometer failed to init: %s", e)
gc_collect()

# init wind vane
try:
    vane = wind.Vane(vane_pin, 0, 3.3, 0)
except Exception as e:
    got_vane = False
    log.warning("Wind vane failed to init: %s", e)
gc_collect()

# init rain gauge


# ===== read queryable sensors

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
            log.info("BME680: T={:.1f}°F H={:.0f}% P={:.3f}mBar G={:.3f}kΩ".format(
                t*1.8+32, h, p, gas/1000))
            (data['t_bme680'], data['h_bme680'], data['p_bme680'], data['g_bme680']) = \
                    (t, h, p/1000, gas)
        # read the si7021
        if got_si7021:
            await asyncio.sleep_ms(si7.convert()+2)
            (t, h) = si7.read_temp_humi()
            log.info("Si7021: T={:.1f}°F H={:.0f}%".format(t*1.8+32, h))
            (data['t_si7021'], data['h_si7021']) = (t, h)
        # read sht31
        if got_sht31:
            await asyncio.sleep_ms(sh3.convert()+2)
            (t, h) = sh3.read_temp_humi()
            log.info("SHT31 : T={:.1f}°F H={:.0f}%".format(t*1.8+32, h))
            (data['t_sht31'], data['h_sht31']) = (t, h)
        # read wind
        if got_anemo:
            (w, g) = anemo.read()
            info = "Wind  : {:.0fmph} gust:{:.0fmph}".format(w, g)
            (data['wind'], data['gust']) = (w, g)
            if got_vane:
                d = vane.read()
                info += " dir={.0f}°".format(d)
                data['wdir'] = d
            log.info(info)
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
            log.debug("pub: %s", data)
            await client.publish(TOPIC+"/sensors", json.dumps(data), qos = 1)

        # display data
        display.fill(0)
        display.text("BME {:.1f}F {:.0f}%".format(data['t_bme680']*1.8+32, data['h_bme680']), 0, 0)
        display.text("    {:.0f}mB {:.0f}kO".format(data['p_bme680']*1000, data['g_bme680']/1000), 0, 9)
        display.text("SHT {:.1f}F {:.0f}%".format(data['t_sht31']*1.8+32, data['h_sht31']), 0, 18)
        display.text("Si  {:.1f}F {:.0f}%".format(data['t_si7021']*1.8+32, data['h_si7021']), 0, 27)
        display.show()

        # keep the dog sleeping
        #global wdt_query_sensors
        #wdt_query_sensors = time.ticks_ms()

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
        gc_collect()

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
                log.info("PMSx003: D={:d}µg/m³ X={:d}".format(pm2_5[0], pm2_5[1]))
                pm2_5 = p3.read()
        # sleep
        global wdt_poll_uarts
        wdt_poll_uarts = time.ticks_ms()
        await asyncio.sleep_ms(500)

# ===== main task

async def start(mqclient):
    loop = asyncio.get_event_loop()
    loop.create_task(query_sensors(mqclient))
    loop.create_task(poll_uarts(mqclient))
