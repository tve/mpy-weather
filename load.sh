#! /bin/bash -ex
cd $(dirname $0)
pyboard -f cp board_config.py :
pyboard -f mkdir src || true
pyboard -f cp src/weather.py :src/
cd ../mpy-mqtt
pyboard -f cp board/board.py board/boot.py board/logging.py board/main.py \
    mqtt_async/mqtt_async.py mqrepl/mqrepl.py :


