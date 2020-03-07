import rain, machine, math, time
print("Starting rain test")

class Counter:
    def __init__(self): self.v = 0
    def value(self): return self.v

rain_ctr = Counter()

if True:
    rain = rain.Rain(rain_ctr)
    start = time.mktime((2020, 3, 6, 9, 0, 0, 4, 0))
    print("Starting at", time.localtime(start))
    now = start
    cnt = 0

    def eq(a, b):
        if a is None and b is None: return True
        if a is None or b is None: return False
        return abs(a-b) < 0.001

    def p(dt, dc, exp):
        # add dt minutes to time, add dc to count, call rain and check exp expectation
        global now, cnt
        now += dt * 60
        cnt += dc
        got = rain.read(now, cnt)
        if not eq(got[0], exp[0]) or not eq(got[1], exp[1]) or not eq(got[2], exp[2]):
            print("At {} with count {} got {}, expected {}".format((now-start)/(60), cnt, got,
                exp))
            #print(math.isclose(got[0],exp[0]), got[1]==exp[1], got[2]==exp[2], got[2], exp[2],
            #        got[2]-exp[2])

    # Test init
    p(0, 0, (None, None, None))
    # Test no rain
    print("Test no rain")
    for i in range(24*60):
        p(1, 0, (0, 0, 0)) # delay one minute and expect zero rain
    # Test constant rain
    print("Test constant rain")
    sum = 0
    for i in range(10):
        sum += 0.02
        p(1, 2, (0.02*60, sum, sum))
    # Test rain stopping
    print("Test rain stopping")
    last = now
    for i in range(4):
        p(1, 0, ((0.01/(i+1))*60, sum, sum))
    p(1, 0, (0, sum, sum))
    # Test rain event ending
    print("Test rain event end")
    for i in range(12*60-5):
        p(1, 0, (0, sum, sum))
    p(1, 0, (0, 0, sum))
    # Test 8am rain-in-day reset
    print("Test rain day end")
    while time.ticks_diff(now, start) < 47*3600-60:
        p(1, 0, (0, 0, sum))
    print("Ending at", time.localtime(now+60))
    p(1, 0, (0, 0, 0))

    print("--END--")
