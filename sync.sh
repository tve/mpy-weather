#! /bin/bash -e
mqsync <<'EOF'
/lib:
  ../mpy-lib: sntp/sntp.py seven-segments/seg7.py button/aswitch.py sysinfo/sysinfo.py
  ../mpy-lib/esp32-counter: counter.py modpcnt.mpy
  ../mpy-lib/esp32-adccal: esp32_adccal.py modadccal.mpy
  ../mpy-mqtt/board: logging.py board.py mqtt.py
  ../mpy-mqtt/mqrepl: mqrepl.py watchdog.py safemode.py
  ../mpy-mqtt/mqtt_async/mqtt_async.py
/src:
  src: *.py
/:
  #board_config.py
  ../mpy-mqtt/board: boot.py main.py
EOF
echo "Reminder: board_config has not been sync'd"
