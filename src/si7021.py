from machine import Pin, I2C

# Default Address
SI7021_I2C_DEFAULT_ADDR = 0x40

# Commands
CMD_MEASURE_RELATIVE_HUMIDITY_HOLD_MASTER_MODE = const(0xE5)
CMD_MEASURE_RELATIVE_HUMIDITY = const(0xF5)
CMD_MEASURE_TEMPERATURE_HOLD_MASTER_MODE = const(0xE3)
CMD_MEASURE_TEMPERATURE = const(0xF3)
CMD_READ_TEMPERATURE_VALUE_FROM_PREVIOUS_RH_MEASUREMENT = const(0xE0)
CMD_RESET = const(0xFE)
CMD_WRITE_RH_T_USER_REGISTER_1 = const(0xE6)
CMD_READ_RH_T_USER_REGISTER_1 = const(0xE7)
CMD_WRITE_HEATER_CONTROL_REGISTER = const(0x51)
CMD_READ_HEATER_CONTROL_REGISTER = const(0x11)

def _crc(data):
    crc = 0
    for v in data:
        crc = crc ^ v
        for _ in range(8, 0, -1):
            if crc & 0x80: #10000000
                crc <<= 1
                crc ^= 0x131 #100110001
            else:
                crc <<= 1
    return crc

class Si7021(object):
    def __init__(self, i2c_dev, addr=SI7021_I2C_DEFAULT_ADDR):
        self.addr = addr
        self.cbuffer = bytearray(2)
        self.cbuffer[1] = 0x00
        self.i2c = i2c_dev

    def write_command(self, command_byte):
        self.cbuffer[0] = command_byte
        self.i2c.writeto(self.addr, self.cbuffer)

    def convert(self):
        """
        Start conversion of temperature and humidity, return ms to wait for result
        """
        self.write_command(CMD_MEASURE_RELATIVE_HUMIDITY)
        return 23

    def read_temp_humi(self):
        # read humidity from conversion command
        raw = self.i2c.readfrom(self.addr, 3)
        if _crc(raw[0:2]) != raw[2]:
            raise RuntimeError("SI7021: CRC mismatch, raw:" + "".join("\\x%02x" % i for i in raw) + \
                    " calculated:" + "%x" % _crc(raw[0:2]))
            return None, None
        rh = (raw[0] << 8) | raw[1]
        rh = (125 * rh / 65536) - 6
        # issue command to read temperature
        self.write_command(CMD_READ_TEMPERATURE_VALUE_FROM_PREVIOUS_RH_MEASUREMENT)
        raw = self.i2c.readfrom(self.addr, 2) # No CRC for this command, weird!
        temp = (raw[0] << 8) | raw[1]
        temp = (175.72 * temp / 65536) - 46.85
        return temp, rh
