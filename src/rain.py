import time

class Rain:
    """
    Rain implements methods to measure rainfall using a tipping bucket gauge.
    """

    RATE_OFF = const(5*60) # force rain rate to zero if no tip in this many seconds
    EVENT_OFF = const(12*60*60) # reset rain event if no tip in this many seconds
    DAY_START = const(8*60) # start rain day this many minutes after midnight

    def __init__(self, counter, mils=10):
        """
        Initialize the tipping gauge using the provided counter object, which must be init'ed for the
        appropriate pin. Bucket tipping counts are converted to inches of rain using the mils
        factor: it describes how many 1/1000th of an inch each tip represents. Typically this is the
        value 10 but may depart from that top adjust for calibration.
        """
        if counter == None or counter.value == None:
            raise ValueError('Counter object needed as argument!')
        self.ctr = counter
        self.mils = mils
        # data for rain rate
        self.last_read_at = None
        self.last_tip_at = None
        self.last_tip_count = None # count at last tip
        # data for rain volume for this event
        self.event_start_at = None
        self.event_start_count = None
        # data for rain volume "today", reset at 8am like San Marcos Pass
        self.day_updated_min = None
        self.day_start_count = None

    def read(self, now=None, count=None):
        """
        Reads the rain gauge and returns a 3-tuple with rain rate (in/hr), rain this event (in), and
        rain today (in).
        The now and count parameters are for testing purposes to be able to simulate tips.
        """
        if now is None:
            now = time.time()
        if count is None:
            count = self.ctr.value()
        # Initialize
        if self.last_tip_at == None:
            self.last_read_at = now
            self.last_tip_at = now - RATE_OFF
            self.last_tip_count = count
            return (None, None, None)
        # Update rain rate
        rate = 0
        dt = time.ticks_diff(now, self.last_tip_at)
        if count == self.last_tip_count:
            if dt < RATE_OFF:
                # the gauge recently tipped, calculate average rate since last tip as if it tipped
                # now (provides graceful drop in rain rate)
                rate = self.mils / dt # [mils/sec]
            elif dt > EVENT_OFF:
                self.event_start_at = None
                self.event_start_count = None
        else:
            if dt >= RATE_OFF:
                dt = time.ticks_diff(now, self.last_read_at)
            rate = self.mils * (count - self.last_tip_count) / dt # [mils/sec]
            #print("rate={}mils/sec dc={} dt={}".format(rate, count - self.last_tip_count, dt))
            if self.event_start_at is None:
                self.event_start_at = self.last_read_at
                self.event_start_count = self.last_tip_count
            self.last_tip_at = now
        if rate != 0:
            rate = round(rate * 3.6, 3) # [in/hr]
        # Update rain event
        event = 0
        if self.event_start_at is not None:
            # we are in a rain event
            event = self.mils * (count - self.event_start_count) / 1000.0
        # Update rain today
        lt = time.localtime(now)
        minute = lt[3]*60 + lt[4] # minutes since midnight
        today = 0
        if self.day_updated_min is None or (self.day_updated_min < DAY_START and minute >= DAY_START):
            self.day_start_count = self.last_tip_count
        today = self.mils * (count - self.day_start_count) / 1000.0
        # Update data
        self.last_read_at = now
        self.last_tip_count = count
        self.day_updated_min = minute
        # that's it...
        return (rate, event, today)
