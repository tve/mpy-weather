Weather station for ESP32 running Micropython
=============================================

This is work-in-progress for a weather station built around an ESP32 running Micropython.
The sensors are:
- bme680 temperature, humidity, pressure, VOC sensor
- sht31 temperature, humidity sensor
- si7021 temperature, humidity sensor
- PMS X003 particulate sensor
- Davis instruments tipping rain gauge
- Inspeed wind vane and anemometer

The weather station sends data to:
- MQTT (for local processing in node-red)
- CWOP (Citizen's Weather) via APRS
- Wunderground

This repository contain work-in-progress.

Source code
-----------
- This app requires micropython 1.12 or later, and most likely the version in
  https://github.com/tve/micropython/tree/tve
- The `.py` files in the top-level directory should be copied to the board's top-level. They are
  expected not to change over the lifetime of the board.
- The `.py` files in the src subdir contain the bulk of the weather station code and should be
  copied into a src subdir on the board. These files are expected to change (improve!) with releases
  of this repo.
- A lib dir also needs to be created on the board with specific libraries from my mpy-lib repo.
