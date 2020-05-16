#! /bin/bash -ex
cd $(dirname $0)
pyboard -f cp board_config.py :
pyboard -f mkdir src >/dev/null || echo src exists
pyboard -f mkdir lib >/dev/null || echo lib exists
pyboard -f cp src/weather.py :src/
(cd ../mpy-mqtt; pyboard -f cp board/boot.py board/main.py :)
(cd ../mpy-mqtt; pyboard -f cp board/board.py board/logging.py mqtt_async/mqtt_async.py \
    board/mqtt.py mqrepl/mqrepl.py mqrepl/watchdog.py mqrepl/safemode.py :/lib/)
if [[ "$1" == "-a" ]]; then
    pyboard -f cp src/*.py :src/
    pyboard -f cp ../micropython/drivers/display/ssd1306.py :/lib/
    (cd ../mpy-lib; pyboard -f cp sntp/sntp.py seven-segments/seg7.py button/aswitch.py \
	esp32-counter/counter.py esp32-counter/modpcnt.mpy \
	esp32-adccal/esp32_adccal.py esp32-adccal/modadccal.mpy \
	:/lib/)
fi
