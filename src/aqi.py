# Formulas from https://en.wikipedia.org/wiki/Air_quality_index
from math import log2

num_steps = const(6)
# AQI steps
aqi_steps = [50, 100, 150, 200, 300, 500]
# AQI colors TODO: fix missing colors!
aqi_colors = [(0,228,0), (255,255,0), (255,126,0), (255,0,0), (143,63,151), (126,0,35)]

# TODO: fix number of color steps!
def aqi_color(aqi):
    if aqi > aqi_steps[num_steps-1]: return aqi_colors[num_steps-1]
    ix = 0
    while aqi > aqi_steps: ix += 1
    return aqi_colors[ix]

# Walk AQI table and interpolate
def aqi_walk(val, table):
    if val > table[num_steps-1]: return aqi_steps[num_steps-1]
    C_low, I_low = 0, 0
    ix = 0
    #print("aqi_walk({}) table[ix]={}".format(val, table[ix]))
    while val > table[ix]:
        C_low = table[ix]+0.1
        I_low = aqi_steps[ix]+1
        ix += 1
    I_high = aqi_steps[ix]
    C_high = table[ix]
    aqi = (I_high-I_low) / (C_high-C_low) * (val - C_low) + I_low
    return int(aqi + 0.5)

# AQI for PM2.5 concentration breakpoints
aqi_pm25_tab = [12.0, 35.4, 55.4, 150.4, 250.4, 500.4]
# AQI based on PM2.5 concentration in ug/m^3
def pm25(pm25): return aqi_walk(pm25, aqi_pm25_tab)

# AQI for BME680 resistance breakpoints (uses negative value due to inverse scale)
# Adapted from https://forums.pimoroni.com/t/bme680-observed-gas-ohms-readings/6608
aqi_tvoc_bme680_tab = [420000, 210000, 105000, 55000, 27500, 13500] #, 8000]
aqi_tvoc_bme680_tab = [20-log2(t) for t in aqi_tvoc_bme680_tab]
# -> [1.319969, 2.319971, 3.319969, 4.252855, 5.252856, 6.279328]
# AQI based on BME680 resistance in Ohm
def tvoc_bme680(resist):
    r = 20-log2(resist)
    if r < 0: r = 0
    return aqi_walk(r, aqi_tvoc_bme680_tab)
