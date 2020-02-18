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
