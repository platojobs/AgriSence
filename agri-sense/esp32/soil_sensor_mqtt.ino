/*
 * AgriSense - ESP32 土壤湿度传感器 MQTT 上报固件
 *
 * 依赖库（Arduino IDE 库管理器安装）：
 *   - PubSubClient
 *   - ArduinoJson
 *
 * 校准说明：
 *   1. 把传感器探头放在空气中，打开串口监视器读取 analogRead(SOIL_PIN) 的值，
 *      填入 DRY_VALUE（干燥时原始值较大）。
 *   2. 把探头浸入水中，读取 analogRead(SOIL_PIN) 的值，填入 WET_VALUE
 *      （湿润时原始值较小）。
 *   3. map() 会把原始值线性映射为 0~100% 的墒情百分比。
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// ★ 用户修改：WiFi 信息
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// ★ 用户修改：MQTT Broker 地址（运行 Mosquitto 的电脑局域网 IP）
const char* mqtt_server = "192.168.1.100";
const int mqtt_port = 1883;

// ★ 用户修改：根据实际传感器校准
const int DRY_VALUE = 3000;  // 空气中读到的原始值（干燥）
const int WET_VALUE = 1200;  // 水中读到的原始值（湿润）
const int SOIL_PIN = 34;     // 土壤湿度传感器模拟输入引脚
const int LED_PIN = 2;       // 板载 LED，用于状态指示

WiFiClient espClient;
PubSubClient client(espClient);
const char* device_id = "esp32_001";
const char* mqtt_topic = "sensors/esp32_001/data";

void setup_wifi() {
  delay(10);
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(ssid);

  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("");
  Serial.println("WiFi connected");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
}

void reconnect() {
  // 循环直到重连成功
  while (!client.connected()) {
    Serial.print("Connecting MQTT...");
    if (client.connect(device_id)) {
      Serial.println("connected");
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" try again in 2 seconds");
      delay(2000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);

  setup_wifi();
  client.setServer(mqtt_server, mqtt_port);
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  // 读取土壤湿度原始值并映射为百分比
  int raw = analogRead(SOIL_PIN);
  int percent = map(raw, DRY_VALUE, WET_VALUE, 0, 100);
  percent = constrain(percent, 0, 100);

  // 构造 JSON 报文
  StaticJsonDocument<200> doc;
  doc["device_id"] = device_id;
  doc["soil_moisture"] = percent;
  doc["raw"] = raw;
  doc["timestamp"] = millis() / 1000;

  char buffer[200];
  serializeJson(doc, buffer);

  // 发布到 MQTT
  client.publish(mqtt_topic, buffer);
  Serial.print("Published: ");
  Serial.println(buffer);

  // LED 翻转指示
  digitalWrite(LED_PIN, !digitalRead(LED_PIN));

  delay(10000);
}
