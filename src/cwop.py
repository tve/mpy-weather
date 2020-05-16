import socket, logging, sys

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)
_ipaddr = None
_config = None

# send a weather report to CWOP via APRS-I servers
# config must have: usr, sta, server, coord
async def send_wx(
    temp=None,  # temperature in centigrade
    hum=None,  # humidity in percent
    winddir=None,  # wind direction in degrees
    windspeed=None,  # wind speed in mph
    windgust=None,  # wind gust speed in mph
    rainrate=None,  # rain in the past hour in 0.01in
    rainevent=None,  # rain "today" in 0.01in
    baro=None,  # barometric pressure in Bar
):
    global _ipaddr, _config
    if not _config:
        return
    if winddir is not None:
        data = "_%03d" % winddir
    else:
        data = "_..."
    if windspeed is not None:
        data += "/%03d" % windspeed
    else:
        data += "/..."
    if windgust is not None:
        data += "g%03d" % windgust
    if temp is not None:
        data += "t%03d" % (temp * 1.8 + 32)
    if hum == 100:
        data += "h00"  # 100% represented as 00
    elif hum:
        data += "h%02d" % hum
    if rainrate is not None:
        data += "r%03d" % rainrate
    if rainevent is not None:
        data += "p%03d" % rainevent
    if baro:
        data += "b%05d" % (baro * 10000 + _config["baro_off"] * 10)
    # L000 = luminosity (in watts per square meter) 999 and below.
    # l000 = luminosity (in watts per square meter) 1000 and above.
    # content = "%s\r\n%s>%s,TCPIP*:@000000z%s%sXTvEWx\r\n" % (
    data = "%s>APESPW,TCPIP*:!%s%sXTvEWx" % (_config["sta"], _config["coord"], data)
    content = _config["usr"] + "\r\n" + data
    try:
        if _ipaddr is None:
            _ipaddr = socket.getaddrinfo(_config["server"], 8080)[0][-1]

        log.debug("To %s: %s", _ipaddr[0], data)
        s = socket.socket()
        s.settimeout(30)
        s.connect(_ipaddr)
        s.write("POST / HTTP/1.0\r\nHost:")
        s.write(_config["server"])
        s.write(
            "\r\nContent-Type: application/octet-stream\r\n"
            "Accept-Type: text/plain\r\nContent-Length:"
        )
        s.write(str(len(content)))
        s.write("\r\n\r\n")
        s.write(content)

        line = s.readline()
        # print(l)
        line = line.split(None, 2)
        status = int(line[1])
        if status >= 200 and status < 300:
            log.info("Posted %s", data)
        else:
            log.warning("POST error %d: %s", status, line[-1].decode("utf-8").strip())
            if status >= 500:
                _ipaddr = None
    except OSError as e:
        _ipaddr = None
        log.exception(logging.WARNING, e, "POST failed:")
    finally:
        s.close()


def start(mqtt, config):
    global _config
    _config = config
