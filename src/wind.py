import machine, time, logging
import uasyncio as asyncio
from esp32_adccal import ADCCal

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class Anemo:
    """
    Anemo implements functions to determine average wind speed and gust speed as measured by an
    anemometer attached to a pulse counter input pin on an ESP32.
    """

    def __init__(self, counter, fct):
        """
        Initialize the anemometer using the provided counter object, which must be init'ed for the
        appropriate pin. The fct converts the frequency in Hertz (pulses per second) to mph and is
        typically a value around 2.5 to 3.5.
        (Note that fct can be specified for pulses per km/h or per m/s instead and read_wind will
        return the values for that measurement unit.)
        """
        if counter is None or counter.value is None:
            raise ValueError("Counter object needed as argument!")
        self.ctr = counter
        self.ws_at = None  # when wind speed was last measured
        self.ws_count = 0  # count at least measurement
        self.fct = fct * 1000  # convert from pulses per millisecond to mph

    async def _gust_poller(self, gust_ms):
        last_at = time.ticks_ms()
        last_count = self.ctr.value()
        self.wg_max = 0
        while True:
            await asyncio.sleep_ms(gust_ms)
            now = time.ticks_ms()
            count = self.ctr.value()
            speed = (count - last_count) / time.ticks_diff(now, last_at)
            # log.debug("Gust: %d-%d -> %d/s -> %.1f mph", count, last_count, 1000*speed, speed*2500)
            if speed > self.wg_max:
                self.wg_max = speed
            last_at = now
            last_count = count

    def start(self, gust_ms=3000):
        """
        Starts the measurements, including launching a background asyncio poller to measure the
        wind gust speed every gust_ms interval.
        The optional gust_ms parameter specifies over which time period wind speed is averaged for
        the wind-gust metric.
        Note that the NOAA / CWOP standard sampling is: 2 minute average for "wind speed" and
        5 or 8 second average for "wind gust" (see https://www.ndbc.noaa.gov/measdes.shtml).
        """
        asyncio.Loop.create_task(self._gust_poller(gust_ms))

    def read(self):
        """
        Reads the wind speed and returns a tuple with wind-speed and wind-gust, both in mph
        (assuming the fct converts from Hz to mph).
        The wind speed value is the average since the last call to read_wind.
        The wind gust value is the max speed measured over a gust_ms interval (see start method)
        since the last call to read_wind.
        """
        now = time.ticks_ms()
        count = self.ctr.value()
        if self.ws_at is None or time.ticks_diff(now, self.ws_at) < 3000:
            speed = 0
            gust = 0
        else:
            speed = (count - self.ws_count) / time.ticks_diff(now, self.ws_at) * self.fct
            gust = self.wg_max * self.fct
            log.debug(
                "Wind: %d-%d=%d in %dms -> %.1f = %.1f mph",
                count,
                self.ws_count,
                count - self.ws_count,
                time.ticks_diff(now, self.ws_at),
                1000 * (count - self.ws_count) / time.ticks_diff(now, self.ws_at),
                speed,
            )
        self.ws_count = count
        self.ws_at = now
        self.wg_max = 0
        return (speed, gust)


class Vane:
    """
    Vane implements the measurement of wind direction using an analog wind vane that reports
    degrees of rotation (direction) as an analog voltage.
    """

    def __init__(self, pin, v_min, v_max, offset):
        """
        Initialize the wind vane on the provided pin (either number or initialized machine.ADC
        object) and configure it for the provided minimum ADC value, maximum value, and value
        when pointing north.
        """
        if isinstance(pin, int):
            self.pin = machine.ADC(machine.Pin(pin))
            self.pin.atten(machine.ADC.ATTN_11DB)
            self.pin.width(machine.ADC.WIDTH_10BIT)
        else:
            try:
                pin.read()
            except AttributeError:
                raise ValueError("pin does not have read method")
            self.pin = pin
        if v_min < 0 or v_min > 65535 or v_max < 0 or v_max > 65535 or v_min > v_max:
            raise ValueError("Invalid v_min or v_max")
        self.v_min = v_min
        self.v_max = v_max
        self.offset = offset
        self.obs_min = 65535  # observed min
        self.obs_max = 0  # observed max
        self.cal = ADCCal()  # atten=machine.ADC.ATTN_11DB, width=machine.ADC.WIDTH_10BIT)

    def min_max(self):
        """
        Return a tuple of observed min and max values
        """
        return (self.obs_min, self.obs_max)

    def _raw_read(self):
        # oversample 8x and average
        sum = 0
        for _ in range(8):
            sum += self.pin.read()
        val = sum // 8
        val = self.cal.correct(val)
        # adjust observed min/max info
        if val < self.obs_min:
            self.obs_min = val
        if val > self.obs_max:
            self.obs_max = val
        # calculate direction as a fraction 0..1
        frac = (val - self.v_min) / (self.v_max - self.v_min)
        if frac < 0:
            frac += 1
        # return direction in degrees
        # print(val, frac, self.offset)
        return (int(frac * 360) + self.offset) % 360

    def _avg(self, old_dir, new_dir):
        # exponential decaying average, however, adjust so abs(new_dir-old_dir)<=180 to avoid
        # anomaly at 0=360 degrees
        if new_dir - old_dir > 180:
            old_dir += 360
        elif old_dir - new_dir > 180:
            new_dir += 360
        avg_dir = (9 * old_dir + new_dir + 5) // 10
        return avg_dir % 360

    async def _vane_poller(self):
        while True:
            await asyncio.sleep_ms(1000)
            new_dir = self._raw_read()
            self.dir = self._avg(self.dir, new_dir)

    def start(self):
        """
        Starts the measurements, including launching a background asyncio poller to measure the
        wind direction every second.
        """
        self.dir = self._raw_read()
        asyncio.Loop.create_task(self._vane_poller())

    def read(self):
        """
        Return wind direction in degrees from north
        """
        return self.dir
