# AgriSense 智慧农业监测系统

基于 ESP32 + MQTT + Flask + SQLite + jQuery/ECharts 的智慧农业土壤墒情监测与自动灌溉系统。

## 数据流

```
ESP32 读土壤湿度传感器
   ↓ Wi-Fi
发布 MQTT 到 sensors/esp32_001/data
   ↓
Mosquitto Broker
   ↓
Python Flask 后端（paho-mqtt 订阅）→ 解析 JSON → 存入 SQLite
   ↓ REST API
jQuery 前端（每 5 秒 Ajax 轮询）→ 更新卡片 / ECharts / 灌溉状态
```

## 目录结构

```
agri-sense/
├── backend/
│   ├── app.py              # Flask 主应用（MQTT 订阅 + REST API）
│   ├── config.py           # 全局配置（MQTT/Flask/阈值）
│   ├── database.py         # SQLite 读写封装
│   ├── irrigation_logic.py # 灌溉决策纯函数
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── css/style.css
│   └── js/
│       ├── dashboard.js    # 实时数据轮询
│       ├── chart.js        # ECharts 历史趋势
│       └── control.js      # 阈值/手动控制/日志
├── esp32/
│   └── soil_sensor_mqtt.ino
└── mosquitto/
    └── mosquitto.conf
```

## 一、环境准备

- **Python 3.7+**
- **Mosquitto MQTT Broker**
- **Arduino IDE**（需安装 ESP32 开发板管理器，以及 `PubSubClient`、`ArduinoJson` 库）

## 二、启动 Mosquitto

使用项目自带的配置文件启动：

**Windows：**
```bash
mosquitto -c mosquitto/mosquitto.conf -v
```

**Mac：**
```bash
mosquitto -c mosquitto/mosquitto.conf -v
```

**Linux：**
```bash
mosquitto -c mosquitto/mosquitto.conf -v
```

启动成功后控制台应显示监听 `1883` 端口。

## 三、启动后端

```bash
cd backend
pip install -r requirements.txt
python app.py
```

控制台应打印：
```
MQTT connected, rc= 0
 * Running on http://0.0.0.0:5000
```

> 注意：`app.py` 中 `use_reloader=False` 已设置，避免 MQTT 线程重复启动。

## 四、打开前端

直接双击 `frontend/index.html`，或启动一个本地服务器：

```bash
cd frontend
python -m http.server 8080
```

浏览器访问 `http://localhost:8080`。

> 注意：`frontend/js/dashboard.js` 中的 `API_BASE` 需与后端地址一致，默认 `http://localhost:5000`。后端已开启 CORS，无需额外配置。

## 五、烧录 ESP32

1. 用 Arduino IDE 打开 `esp32/soil_sensor_mqtt.ino`。
2. 修改以下用户配置：
   - WiFi 名称与密码
   - MQTT Broker 地址（运行 Mosquitto 的电脑局域网 IP）
   - `DRY_VALUE` / `WET_VALUE` 校准值（见下方校准说明）
3. 选择正确的开发板与端口，点击上传。
4. 打开串口监视器（波特率 `115200`），应看到：
   ```
   WiFi connected
   IP address: 192.168.x.x
   Connecting MQTT...connected
   Published: {"device_id":"esp32_001","soil_moisture":42,"raw":1850,"timestamp":123}
   ```

**传感器校准：**
- 把探头放在空气中，串口读取 `analogRead(SOIL_PIN)` 的值，填入 `DRY_VALUE`（干燥时原始值较大）。
- 把探头浸入水中，读取值填入 `WET_VALUE`（湿润时原始值较小）。
- `map()` 会把原始值线性映射为 0~100% 的墒情百分比。

## 六、无硬件测试

没有 ESP32 也可以用 MQTT 客户端模拟数据上报。

使用 `mosquitto_pub`：
```bash
mosquitto_pub -h localhost -t sensors/esp32_001/data -m '{"device_id":"test","soil_moisture":25,"raw":2000,"timestamp":123}'
```

或使用 MQTTX 等图形化工具，向 `sensors/esp32_001/data` 发布相同 JSON。

预期效果：
- 前端土壤墒情卡片在 5 秒内显示 `25%`。
- 因 `25 < 30`（默认下限），卡片变为黄色左边框并闪烁，灌溉状态显示「土壤墒情低于下限」。

## 七、常见问题

| 现象 | 排查方向 |
|------|----------|
| MQTT 连不上 | 检查 Broker IP 是否正确、防火墙是否放行 1883 端口、Mosquitto 是否在运行 |
| 前端无数据 | 检查 `dashboard.js` 中 `API_BASE` 是否与后端地址一致；后端是否已启动；浏览器控制台是否有 CORS 报错 |
| ESP32 读数恒定 | 检查传感器接线与引脚号；重新校准 `DRY_VALUE`/`WET_VALUE`；确认探头未短路 |
| 后端启动报错 | 确认已 `pip install -r requirements.txt`；确认 Mosquitto 已先启动（否则 MQTT 连接失败但 Flask 仍可启动） |

## 八、REST API 一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/sensors/latest` | 最新读数 + 灌溉决策 |
| GET | `/api/sensors/history?hours=24` | 历史聚合（5 分钟窗口均值） |
| GET | `/api/irrigation/status` | 当前灌溉决策 |
| POST | `/api/irrigation/manual` | 手动控制 `{"action":"start"\|"stop"}` |
| GET | `/api/irrigation/logs` | 最近 20 条灌溉日志 |
| POST | `/api/thresholds` | 保存阈值 `{"low":30,"high":70}` |
