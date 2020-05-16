import machine, time, aqi, logging, gc
import uasyncio as asyncio
import ujson as json
import aswitch, seg7

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

# Devices
bme680 = None
si7021 = None
sht31 = None
pmsx003 = None
anemo = None
vane = None
rain = None
cwop = None
display = None

# PM2.5 sensor averaging
pm_sum = [0, 0]
pm_cnt = 0


# load sensor modules and initialize sensors
def init_sensors(kind):
    global bme680, si7021, sht31, pmsx003, anemo, vane, rain
    global cwop, display

    # ===== pin configuration, see also Projects/kicad/esp32-weather/README.md
    if kind == "lolin-d32":
        scl0, sda0 = 23, 22  # bme680, si7021, sht31
        scl1, sda1 = 18, 4  # oled
        scl2, sda2 = 13, 12  # expansion
        pm_tx, pm_rx = 25, 26  # pmsa003
        anemo_pin = 39  # anemometer pulse
        vane_pin = 36  # wind vane analog
        rain_pin = 34  # rain pulse
        pow_3v3 = 32  # active-low power for anemo/vane/rain/pmsa003
    else:
        raise ("Unknown board kind: " + kind)

    # ===== init devices

    # show splash screen on display
    from ssd1306 import SSD1306_I2C

    try:
        scl1_pin = machine.Pin(scl1)
        sda1_pin = machine.Pin(sda1)
        display = SSD1306_I2C(128, 64, machine.I2C(scl=scl1_pin, sda=sda1_pin, freq=1000000))
        display.fill(1)
        display.fill_rect(10, 10, 108, 44, 0)
        display.text("WCC Weather", 20, 20, 1)
        display.show()
    except Exception as e:
        display = None
        log.warning("No display: %s", e)

    # start power for anemo, vane, etc.
    pow_3v3_pin = machine.Pin(pow_3v3, machine.Pin.OUT)
    pow_3v3_pin(0)

    # I2C bus for primary sensors
    scl0_pin = machine.Pin(scl0)
    sda0_pin = machine.Pin(sda0)
    i2c0_dev = machine.I2C(scl=scl0_pin, sda=sda0_pin, freq=100000)

    # BME680 temperature/humidity/pressure/voc
    from bme680 import BME680

    try:
        bme680 = BME680(i2c0_dev)
        bme680.set_gas_heater_temperature(320)
        bme680.set_gas_heater_duration(100)
        log.info("Found BME680")
    except Exception as e:
        bme680 = None
        log.warning("No BME680 found: %s", e)

    # SI7021 temperature/humidity
    from si7021 import Si7021

    try:
        si7021 = Si7021(i2c0_dev)
        si7021.convert()
        log.info("Found Si7021")
    except Exception as e:
        si7021 = None
        log.warning("No Si7021 found: %s", e)

    # SHT31 temperature/humidity
    from sht31 import SHT31

    try:
        sht31 = SHT31(i2c0_dev)
        sht31.convert()
        log.info("Found SHT31")
    except Exception as e:
        sht31 = None
        log.warning("No SHT31 found: %s", e)

    # PMSx003 PM sensor
    from pms_x003 import PMSx003

    try:
        pmsx003 = PMSx003(tx=pm_tx, rx=pm_rx)
        log.info("Found PMSx003")
    except Exception as e:
        pmsx003 = None
        log.warning("No PMSx003 found: %s", e)

    # Anemometer and wind vane
    from wind import Anemo, Vane
    from counter import Counter

    try:
        # configure pin with pull-up
        machine.Pin(anemo_pin, mode=machine.Pin.IN)
        anemo_ctr = Counter(0, anemo_pin)
        anemo_ctr.filter(10)  # 10us filter
        anemo = Anemo(anemo_ctr, 2.5)  # 2.5 mph per Hz
        anemo.start()
    except Exception as e:
        anemo = None
        log.exc(e, "Anemometer failed to init")
    try:
        vane = Vane(vane_pin, 140, 1600, 15)
        vane.start()
    except Exception as e:
        vane = None
        log.exc(e, "Wind vane failed to init")

    # init rain gauge
    pass

    # init CWOP
    try:
        from cwop import send_wx

        cwop = send_wx
    except ImportError:
        log.warning("Cannot import CWOP, skipping")


# ===== read queryable sensors

mode = 0  # values 0 .. mode_max+1
mode_led = None
mode_max = const(3)  # largest "debug" value, mode_max+1 is used to switch back to 0
mode_period = (0, 500, 4000, 4000, 500)  # milliseconds sleep per mode


async def mode_blink(ms=100):
    mode_led(1 - mode_led())
    await asyncio.sleep_ms(ms)
    mode_led(1 - mode_led())


async def next_mode(pin):
    global mode
    # new mode assuming long press (mode_max+1 reverts to 0 after first display)
    m = mode_max + 1 if mode > 0 else 1
    # check for long press
    for i in range(10):
        await asyncio.sleep_ms(100)
        if pin.value():
            # user let go of button -> short press
            if mode:
                m = mode % mode_max + 1  # cycle among test modes
            else:
                m = 0  # stay in normal run mode
            break
    mode = m
    #
    if display:
        display.fill(1)
        seg7.draw_number(display, str(mode % (mode_max + 1)), 50, 10, 24, 48, 0, 3)
        display.show()
    #
    log.info("MODE = %d", mode)


async def query_sensors(client, topic, interval):
    global bme680, si7021, sht31, pmsx003, anemo, vane, rain
    global cwop, display
    global pm_cnt, pm_sum
    global mode
    t0 = time.ticks_ms()
    while True:
        data = {}
        gas, pm25 = None, None
        # convert the bme680
        if bme680:
            await asyncio.sleep_ms(bme680.convert())
            while not bme680.ready():
                await asyncio.sleep_ms(10)
            (t, h, p, gas) = bme680.read_data()
            tF = t * 1.8 + 32
            log.info("BME680 : T=%.1f°F H=%.0f%% P=%.3fmBar G=%.3fkΩ", tF, h, p, gas / 1000)
            (data["t_bme680"], data["h_bme680"]) = (t, h)
            (data["p_bme680"], data["g_bme680"]) = (p / 1000, gas)
        # read the si7021
        if si7021:
            await asyncio.sleep_ms(si7021.convert() + 2)
            (t, h) = si7021.read_temp_humi()
            log.info("Si7021 : T=%.1f°F H=%.0f%%", t * 1.8 + 32, h)
            (data["t_si7021"], data["h_si7021"]) = (t, h)
        # read sht31
        if sht31:
            await asyncio.sleep_ms(sht31.convert() + 2)
            (t, h) = sht31.read_temp_humi()
            log.info("SHT31  : T=%.1f°F H=%.0f%%", t * 1.8 + 32, h)
            (data["t_sht31"], data["h_sht31"]) = (t, h)
        # read wind
        if anemo:
            (w, g) = anemo.read()
            logstr = "Wind   : %.0fmph gust:%.0fmph"
            logvars = [w, g]
            (data["wind"], data["gust"]) = (w, g)
            if vane:
                d = vane.read()
                logstr += " dir=%0f°"
                logvars.append(d)
                data["wdir"] = d
            log.info(logstr, *logvars)
        # read rain gauge
        # TODO!

        # insert averaged dust data
        if pm_cnt > 0:
            d = [v / pm_cnt for v in pm_sum]
            pm25 = d[0]
            data["pm25"] = pm25
            log.info("PMSx003: D=%.1fµg/m³ X=%.1f", d[0], d[1])
            pm_sum = [0 for _ in pm_sum]
            pm_cnt = 0

        # AQI conversions
        if gas is not None:
            data["aqi_tvoc"] = aqi.tvoc_bme680(gas)
        if pm25 is not None:
            data["aqi_pm25"] = aqi.pm25(pm25)

        if display:
            display.fill(0)
            if mode == 1:
                # Test mode for wind vane
                wdir = data.get("wdir", -1)
                display.text("Wind dir: %d" % wdir, 0, 0)
                wdir_str = "%3do" % wdir
                seg7.draw_number(display, wdir_str, 10, 14, 18, 48, 1, 3)

            elif mode == 2:
                # Test mode for wind speed
                wspd = data.get("wind", -1)
                display.text("Wind: %.1f mph" % wspd, 0, 0)
                wspd_str = "%4.1f" % wspd
                seg7.draw_number(display, wspd_str, 10, 14, 18, 48, 1, 3)

            # else mode == 3: # regular function is rapid update test mode, "falls thru" into else
            # else mode == 4: # regular function 1 quick update then switch to mode 0, "falls thru"

            else:
                # Regular operating mode, display lots of data and send it too

                # publish data
                if mode == 0 and any(d is not None for d in data):
                    log.info("pub: %s", data)
                    await client.publish(topic, json.dumps(data), qos=1, sync=False)

                # display data
                display.text(
                    "BME {:.1f}F {:.0f}%".format(data["t_bme680"] * 1.8 + 32, data["h_bme680"]),
                    0,
                    0,
                )
                display.text(
                    "    {:.0f}mB {:.0f}kO".format(
                        data["p_bme680"] * 1000, data["g_bme680"] / 1000
                    ),
                    0,
                    9,
                )
                display.text(
                    "SHT {:.1f}F {:.0f}%".format(data["t_sht31"] * 1.8 + 32, data["h_sht31"]),
                    0,
                    18,
                )
                display.text(
                    "Si  {:.1f}F {:.0f}%".format(data["t_si7021"] * 1.8 + 32, data["h_si7021"]),
                    0,
                    27,
                )
                display.text("PM  {:.1f} Rn {:.2f}".format(data.get("pm25", -1), 0), 0, 36)
                display.text(
                    "Wnd {:.0f} {:3d}*".format(data.get("wind", -1), data.get("wdir", -1)), 0, 45
                )
                display.text("Free {:d} {:d}".format(gc.mem_free(), gc.mem_maxfree()), 0, 54)

            await mode_blink()
            display.show()

        if mode == 0 and cwop:
            asyncio.get_event_loop().create_task(
                cwop(
                    temp=data.get("t_bme680", None),
                    hum=data.get("h_bme680", None),
                    baro=data.get("p_bme680", None),
                    winddir=data.get("wdir", None),
                    windspeed=data.get("wind", None),
                    windgust=data.get("gust", None),
                )
            )

        # sleep
        iv = interval
        while True:
            t1 = time.ticks_ms()
            dt = time.ticks_diff(t1, t0)
            if dt >= iv or mode and dt > mode_period[mode]:
                break
            await asyncio.sleep_ms(min(iv - dt, 500))
        if dt >= iv and dt < iv * 3 / 2:
            t0 = time.ticks_add(t0, iv)
        else:
            t0 = time.ticks_ms()
        if mode > mode_max:  # hack to get mode 0 to display immediately when switching to it
            mode = 0


# ===== read uart sensors that send data when they please


async def poll_uarts(client):
    global pm_sum, pm_cnt
    while True:
        # read the PMSA003
        if pmsx003:
            pm2_5 = pmsx003.read()
            while pm2_5 is not None:
                for i, v in enumerate(pm2_5):
                    pm_sum[i] += v
                pm_cnt += 1
                log.debug("PMSx003: D=%dµg/m³ X=%d", pm2_5[0], pm2_5[1])
                pm2_5 = pmsx003.read()
        # sleep
        # global wdt_poll_uarts
        # wdt_poll_uarts = time.ticks_ms()
        await asyncio.sleep_ms(500)


# ===== main task


def start(mqtt, config):
    init_sensors(config["kind"])
    loop = asyncio.get_event_loop()
    interval_ms = config["interval"] * 1000
    loop.create_task(query_sensors(mqtt.client, config["prefix"] + "/sensors", interval_ms))
    loop.create_task(poll_uarts(mqtt.client))
    if "mode_pin" in config:
        mode_pin = machine.Pin(config["mode_pin"], machine.Pin.IN)
        mode_sw = aswitch.Switch(mode_pin)
        mode_sw.debounce_ms = 100
        mode_sw.close_func(next_mode, [mode_pin])
        log.debug("mode button init")
    if "mode_led" in config:
        global mode_led
        mode_led = machine.Pin(config["mode_led"], machine.Pin.OUT, value=1)
        loop.create_task(mode_blink(500))
        log.debug("mode LED init on pin %d", config["mode_led"])
