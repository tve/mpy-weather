# board_config contains magic strings that don't get published or checked into source control
# it establishes this board's identity as well as secret strings to connect to the world
from binascii import unhexlify

# kind tells us which type of board this is running
#kind = "lolin-d32"
kind = "huzzah32"

# location is the system name and is used in mqtt topics, etc
location = "mqtest"

# info to connect to wifi
wifi_ssid = 'my-ssid'
wifi_pass = 'my-pass'

# info to connect to mqtt broker (using TLS-PSK crypto/auth)
mqtt_server = '192.168.0.1'
mqtt_ident = 'esp32-test'
mqtt_key = unhexlify(b'd9000000000000000000000000000024')
