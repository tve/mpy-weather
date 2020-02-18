import machine
import ustruct as struct

# From https://github.com/pkucmus/micropython-pms7003
# Hacked down to just return the PM2.5 concentration

#PMS_PM1_0 = 0
#PMS_PM2_5 = 1
#PMS_PM10_0 = 2
#PMS_PM1_0_ATM = 3
PMS_PM2_5_ATM = 4 # PM2.5 concentration ug/m3 ("atmospheric" environment)
#PMS_PM10_0_ATM = 5
PMS_PCNT_0_3 = 6
#PMS_PCNT_0_5 = 7
#PMS_PCNT_1_0 = 8
PMS_PCNT_2_5 = 9
#PMS_PCNT_5_0 = 10
#PMS_PCNT_10_0 = 11
#PMS_VERSION = 12
#PMS_ERROR = 13
PMS_CHECKSUM = 14

# parsing states
S_INIT = 0    # looking for start char (0x42)
S_STARTED = 1 # looking for second char (0x4D)
S_LEN = 2     # ready to read packet length
S_DATA = 3    # ready to read packet body & checksum

from machine import Pin
trig = Pin(12, Pin.OUT)
trig(0)

class PMSx003:

    def __init__(self, uart=2, tx=3, rx=4):
        self._uart = machine.UART(2, 9600, tx=tx, rx=rx)
        self._uart.init(9600, bits=8, parity=None, stop=1)
        self._state = S_INIT
        print(self._uart)

    def _assert_byte(self, byte, expected):
        if byte is None or len(byte) < 1 or ord(byte) != expected:
            return False
        return True

    def read(self):
        cnt = self._uart.any()
        if (cnt > 250):
            print("PMSx003: uart overrun")
            self._uart.read(300)
            return None
        if cnt == 0: return None
        # read first header char
        while self._state == S_INIT:
            if cnt == 0: return None
            if self._assert_byte(self._uart.read(1), 0x42):
                self._state = S_STARTED
            cnt -= 1
        # read second header char
        if self._state == S_STARTED:
            if cnt == 0: return None
            if not self._assert_byte(self._uart.read(1), 0x4D):
                self._state = S_INIT
                return None
            cnt -= 1
            self._state = S_LEN
        # read packet length
        if self._state == S_LEN:
            if cnt < 2: return None
            hdr = self._uart.read(2)
            if len(hdr) != 2:
                print('PMSx003: len vanished')
                self._state = S_INIT
                return None
            ll = hdr[0]*256+hdr[1]
            cnt -= 2
            #print("PMSx003: len={}".format(ll))
            if ll != 2*13+2:
                print("PMSx003: bad length ({})".format(ll))
                self._state = S_INIT
                return None
            self._state = S_DATA
        # read packet body
        if self._state == S_DATA:
            if cnt < 28:
                return None
            read_buffer = self._uart.read(28)
            self._state = S_INIT
            if len(read_buffer) != 28:
                print('PMSx003: data vanished')
                return None
            if False:
                for i in range(len(read_buffer)):
                    print('0x{:02x} '.format(read_buffer[i]), end='')
                print(" (cnt={})".format(cnt-28))
            data = struct.unpack('!HHHHHHHHHHHHBBH', read_buffer)
            # verify checksum
            checksum = 0x42 + 0x4D + 28
            for c in read_buffer[0:26]:
                checksum += c
            if checksum == data[PMS_CHECKSUM]:
                #print("PMSx003:", data)
                return (data[PMS_PM2_5_ATM], data[PMS_PCNT_0_3]-data[PMS_PCNT_2_5])
            trig(1)
            print('PMSx003: bad checksum')

        return None

#           {
#                'FRAME_LENGTH': data[self.PMS_FRAME_LENGTH],
#                'PM1_0': data[self.PMS_PM1_0],
#                'PM2_5': data[self.PMS_PM2_5],
#                'PM10_0': data[self.PMS_PM10_0],
#                'PM1_0_ATM': data[self.PMS_PM1_0_ATM],
#                'PM2_5_ATM': data[self.PMS_PM2_5_ATM],
#                'PM10_0_ATM': data[self.PMS_PM10_0_ATM],
#                'PCNT_0_3': data[self.PMS_PCNT_0_3],
#                'PCNT_0_5': data[self.PMS_PCNT_0_5],
#                'PCNT_1_0': data[self.PMS_PCNT_1_0],
#                'PCNT_2_5': data[self.PMS_PCNT_2_5],
#                'PCNT_5_0': data[self.PMS_PCNT_5_0],
#                'PCNT_10_0': data[self.PMS_PCNT_10_0],
#                'VERSION': data[self.PMS_VERSION],
#                'ERROR': data[self.PMS_ERROR],
#                'CHECKSUM': data[self.PMS_CHECKSUM],
#            }
