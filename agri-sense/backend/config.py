# -*- coding: utf-8 -*-
"""
AgriSense 全局配置
"""

# ★ 用户修改：MQTT Broker 地址（Mosquitto 所在电脑的局域网 IP）
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "sensors/+/data"

DATABASE_PATH = "sensor_data.db"

FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5001

# 默认灌溉阈值（可在前端修改后存入内存）
DEFAULT_THRESHOLD_LOW = 30
DEFAULT_THRESHOLD_HIGH = 70
