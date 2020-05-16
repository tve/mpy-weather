import cwop, uasyncio as asyncio

cwop_config = {
    "usr"    : "user N6TVE-11 pass 11394 vers esp-mp-wx 1.00",
    "sta"    : "N6TVE-11",
    "server" : "rotate.aprs2.net",
    "coord"  : "3429.95N/11949.07W",
}

cwop._config = cwop_config
asyncio.run(
    cwop.send_wx(temp=53, hum=70, winddir=325, windspeed=28, windgust=37, baro=9415)
)
