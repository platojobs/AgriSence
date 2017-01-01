# -*- coding: utf-8 -*-
"""
AgriSense 后端主应用
- paho-mqtt 订阅传感器数据并入库
- Flask 提供 REST API 供前端查询与手动控制
"""

import json
import hashlib
import random
import threading
import time

from flask import Flask, request, jsonify
from flask_cors import CORS
import paho.mqtt.client as mqtt

from config import (
    MQTT_BROKER, MQTT_PORT, MQTT_TOPIC,
    FLASK_HOST, FLASK_PORT,
    DEFAULT_THRESHOLD_LOW, DEFAULT_THRESHOLD_HIGH,
)
from database import (
    init_db, insert_reading, get_latest, get_history, get_recent_readings,
    insert_irrigation_log, get_recent_logs,
    get_devices, get_device, upsert_device, delete_device,
    get_alerts, insert_alert, handle_alert,
    get_alert_rules, upsert_alert_rule, delete_alert_rule,
    get_schedules, insert_schedule, update_schedule, delete_schedule,
    get_overview_stats,
    get_actuators, get_actuator, update_actuator, upsert_actuator,
    get_farm_logs, insert_farm_log, delete_farm_log,
    get_batches, get_batch, insert_batch, update_batch_quality,
    get_knowledge, get_knowledge_article,
    get_news, get_news_article,
    insert_feedback,
)
from irrigation_logic import decide

app = Flask(__name__)
CORS(app)

# 灌溉阈值（内存中，可由前端 API 修改）
current_thresholds = {
    "low": DEFAULT_THRESHOLD_LOW,
    "high": DEFAULT_THRESHOLD_HIGH,
}


# ---------------------------------------------------------------------------
# MQTT 回调：只做数据入库，不操作 Flask request 上下文
# ---------------------------------------------------------------------------
def on_connect(client, userdata, flags, rc):
    print("MQTT connected, rc=", rc)
    client.subscribe(MQTT_TOPIC)


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        insert_reading(
            payload.get("device_id", "unknown"),
            payload.get("soil_moisture"),
            payload.get("raw"),
            payload.get("timestamp"),
            temperature=payload.get("temperature"),
            humidity=payload.get("humidity"),
            light=payload.get("light"),
        )
        print("received:", payload)
        # 入库后立即评估规则，实现实时告警
        evaluate_rules()
    except Exception as e:
        print("MQTT parse error:", e)


# ---------------------------------------------------------------------------
# 决策辅助：基于最新读数与当前阈值计算灌溉决策
# ---------------------------------------------------------------------------
def _build_decision(latest):
    """根据最新读数与当前阈值返回决策 dict。"""
    soil_moisture = latest.get("soil_moisture") if latest else None
    action, reason = decide(
        soil_moisture,
        threshold_low=current_thresholds["low"],
        threshold_high=current_thresholds["high"],
    )
    return {
        "decision": action,
        "decision_text": reason,
        "threshold_low": current_thresholds["low"],
        "threshold_high": current_thresholds["high"],
    }


# ---------------------------------------------------------------------------
# 规则引擎：按告警规则评估最新读数，触发时自动生成告警
# ---------------------------------------------------------------------------
ALERT_COOLDOWN = 600  # 同一指标+设备的告警冷却时间(秒)，避免刷屏
_recent_alerts = {}   # {(metric, device_id): last_alert_ts}


def _check_condition(value, condition, threshold):
    """判断单条件是否成立，兼容 lt/gt 与 </> 两种写法。"""
    if value is None:
        return False
    if condition in ("lt", "<"):
        return value < threshold
    if condition in ("gt", ">"):
        return value > threshold
    return False


def evaluate_rules():
    """读取最新读数与启用规则，逐条评估并生成告警。"""
    latest = get_latest()
    if not latest:
        return
    rules = get_alert_rules()
    device_id = latest.get("device_id", "unknown")
    now = int(time.time())

    for rule in rules:
        if not rule.get("enabled"):
            continue
        metric = rule.get("metric")
        value = latest.get(metric)
        if value is None:
            continue
        if not _check_condition(value, rule.get("condition"), rule.get("threshold")):
            continue

        # 冷却检查
        key = (metric, device_id)
        last_ts = _recent_alerts.get(key, 0)
        if now - last_ts < ALERT_COOLDOWN:
            continue

        cond_text = "低于" if rule["condition"] in ("lt", "<") else "高于"
        message = f"{metric} {cond_text} 阈值 {rule['threshold']}（当前值 {value}）"
        insert_alert(metric, rule.get("level", "warning"), message, device_id)
        _recent_alerts[key] = now
        print(f"[RULE] alert generated: {message}")


def _rule_engine_loop():
    """后台线程：每 30 秒评估一次规则。"""
    while True:
        try:
            evaluate_rules()
        except Exception as e:
            print("rule engine error:", e)
        time.sleep(30)


# ---------------------------------------------------------------------------
# REST API
# ---------------------------------------------------------------------------
@app.route("/api/sensors/latest", methods=["GET"])
def api_sensors_latest():
    """最新读数 + 灌溉决策。"""
    latest = get_latest()
    decision = _build_decision(latest)

    result = {
        "device_id": latest.get("device_id") if latest else None,
        "soil_moisture": latest.get("soil_moisture") if latest else None,
        "temperature": latest.get("temperature") if latest else None,
        "humidity": latest.get("humidity") if latest else None,
        "light": latest.get("light") if latest else None,
        "raw": latest.get("raw") if latest else None,
        "timestamp": latest.get("timestamp") if latest else None,
    }
    result.update(decision)
    return jsonify(result)


@app.route("/api/sensors/history", methods=["GET"])
def api_sensors_history():
    """历史聚合数据，默认过去 24 小时。"""
    hours = request.args.get("hours", default=24, type=int)
    data = get_history(hours=hours)
    return jsonify(data)


@app.route("/api/sensors/recent", methods=["GET"])
def api_sensors_recent():
    """最近 N 条原始读数，默认 20 条。"""
    limit = request.args.get("limit", default=20, type=int)
    limit = max(1, min(limit, 500))
    return jsonify(get_recent_readings(limit=limit))


@app.route("/api/irrigation/status", methods=["GET"])
def api_irrigation_status():
    """当前灌溉决策。"""
    latest = get_latest()
    decision = _build_decision(latest)
    return jsonify(decision)


@app.route("/api/irrigation/manual", methods=["POST"])
def api_irrigation_manual():
    """手动控制灌溉。body: {"action": "start" | "stop"}"""
    data = request.get_json(silent=True) or request.form
    action = data.get("action")
    if action not in ("start", "stop"):
        return jsonify({"status": "error", "message": "action 必须为 start 或 stop"}), 400

    reason = "手动触发" if action == "start" else "手动停止"
    insert_irrigation_log(action, reason)
    # 联动灌溉阀门执行器
    valve_status = "on" if action == "start" else "off"
    update_actuator("irrigation_valve", valve_status)
    return jsonify({"status": "ok", "action": action, "valve": valve_status})


@app.route("/api/irrigation/logs", methods=["GET"])
def api_irrigation_logs():
    """最近 20 条灌溉日志。"""
    logs = get_recent_logs(limit=20)
    return jsonify(logs)


@app.route("/api/thresholds", methods=["POST"])
def api_thresholds():
    """保存灌溉阈值。body: {"low": 30, "high": 70}"""
    data = request.get_json(silent=True) or request.form
    try:
        low = float(data.get("low"))
        high = float(data.get("high"))
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "阈值必须为数字"}), 400

    if low >= high:
        return jsonify({"status": "error", "message": "下限必须小于上限"}), 400

    current_thresholds["low"] = low
    current_thresholds["high"] = high
    return jsonify({"status": "ok", "low": low, "high": high})


# ---------------------------------------------------------------------------
# 设备管理 API
# ---------------------------------------------------------------------------
@app.route("/api/devices", methods=["GET"])
def api_devices_list():
    """设备列表。"""
    return jsonify(get_devices())


@app.route("/api/devices", methods=["POST"])
def api_device_upsert():
    """新增/更新设备。body: {device_id, name, location, status}"""
    data = request.get_json(silent=True) or request.form
    device_id = data.get("device_id")
    if not device_id:
        return jsonify({"status": "error", "message": "device_id 必填"}), 400
    upsert_device(
        device_id,
        data.get("name", device_id),
        data.get("location", ""),
        data.get("status", "offline"),
        data.get("last_seen"),
    )
    return jsonify({"status": "ok"})


@app.route("/api/devices/<device_id>", methods=["DELETE"])
def api_device_delete(device_id):
    """删除设备。"""
    delete_device(device_id)
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# 告警 API
# ---------------------------------------------------------------------------
@app.route("/api/alerts", methods=["GET"])
def api_alerts_list():
    """告警列表，?status=pending 过滤。"""
    status = request.args.get("status")
    return jsonify(get_alerts(status=status))


@app.route("/api/alerts/<int:alert_id>/handle", methods=["POST"])
def api_alert_handle(alert_id):
    """处理告警。"""
    handle_alert(alert_id)
    return jsonify({"status": "ok"})


@app.route("/api/alert-rules", methods=["GET"])
def api_alert_rules_list():
    """告警规则列表。"""
    return jsonify(get_alert_rules())


@app.route("/api/alert-rules", methods=["POST"])
def api_alert_rule_upsert():
    """新增/更新告警规则。"""
    data = request.get_json(silent=True) or request.form
    try:
        upsert_alert_rule(
            data.get("metric"),
            data.get("condition"),
            float(data.get("threshold", 0)),
            data.get("level", "warning"),
            int(data.get("enabled", 1)),
            data.get("id"),
        )
        return jsonify({"status": "ok"})
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "参数错误"}), 400


@app.route("/api/alert-rules/<int:rule_id>", methods=["DELETE"])
def api_alert_rule_delete(rule_id):
    """删除告警规则。"""
    delete_alert_rule(rule_id)
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# 灌溉调度 API
# ---------------------------------------------------------------------------
@app.route("/api/irrigation/schedules", methods=["GET"])
def api_schedules_list():
    """灌溉调度列表。"""
    return jsonify(get_schedules())


@app.route("/api/irrigation/schedules", methods=["POST"])
def api_schedule_create():
    """新增灌溉调度。body: {name, start_time, duration, enabled}"""
    data = request.get_json(silent=True) or request.form
    insert_schedule(
        data.get("name", "定时灌溉"),
        data.get("start_time", "06:00"),
        int(data.get("duration", 30)),
        int(data.get("enabled", 1)),
    )
    return jsonify({"status": "ok"})


@app.route("/api/irrigation/schedules/<int:schedule_id>", methods=["PUT"])
def api_schedule_update(schedule_id):
    """更新灌溉调度。"""
    data = request.get_json(silent=True) or request.form
    update_schedule(
        schedule_id,
        data.get("name", "定时灌溉"),
        data.get("start_time", "06:00"),
        int(data.get("duration", 30)),
        int(data.get("enabled", 1)),
    )
    return jsonify({"status": "ok"})


@app.route("/api/irrigation/schedules/<int:schedule_id>", methods=["DELETE"])
def api_schedule_delete(schedule_id):
    """删除灌溉调度。"""
    delete_schedule(schedule_id)
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# 执行器 API
# ---------------------------------------------------------------------------
@app.route("/api/actuators", methods=["GET"])
def api_actuators_list():
    """执行器列表及状态。"""
    return jsonify(get_actuators())


@app.route("/api/actuators/<name>/control", methods=["POST"])
def api_actuator_control(name):
    """控制执行器开关。body: {"status": "on" | "off"}"""
    data = request.get_json(silent=True) or request.form
    status = data.get("status")
    if status not in ("on", "off"):
        return jsonify({"status": "error", "message": "status 必须为 on 或 off"}), 400
    update_actuator(name, status)
    return jsonify({"status": "ok", "name": name, "value": status})


# ---------------------------------------------------------------------------
# 农事日志 API
# ---------------------------------------------------------------------------
@app.route("/api/farm-logs", methods=["GET"])
def api_farm_logs_list():
    """农事日志列表。"""
    return jsonify(get_farm_logs())


@app.route("/api/farm-logs", methods=["POST"])
def api_farm_log_create():
    """新增农事日志。body: {type, description, operator}"""
    data = request.get_json(silent=True) or request.form
    insert_farm_log(
        data.get("type", "其他"),
        data.get("description", ""),
        data.get("operator", "系统"),
    )
    return jsonify({"status": "ok"})


@app.route("/api/farm-logs/<int:log_id>", methods=["DELETE"])
def api_farm_log_delete(log_id):
    """删除农事日志。"""
    delete_farm_log(log_id)
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# 溯源批次 API
# ---------------------------------------------------------------------------
@app.route("/api/traceability/batches", methods=["GET"])
def api_batches_list():
    """溯源批次列表。"""
    return jsonify(get_batches())


@app.route("/api/traceability/batches", methods=["POST"])
def api_batch_create():
    """新增溯源批次。body: {batch_no, crop_name, sowing_date, ...}"""
    data = request.get_json(silent=True) or request.form
    if not data.get("batch_no"):
        return jsonify({"status": "error", "message": "batch_no 必填"}), 400
    insert_batch(
        data["batch_no"],
        data.get("crop_name", ""),
        data.get("sowing_date", ""),
        data.get("harvest_date"),
        data.get("quality_status", "pending"),
        data.get("notes", ""),
    )
    return jsonify({"status": "ok"})


@app.route("/api/traceability/batches/<batch_no>", methods=["GET"])
def api_batch_detail(batch_no):
    """批次详情 + 相关农事日志 + 灌溉记录，构建溯源时间线。"""
    batch = get_batch(batch_no)
    if not batch:
        return jsonify({"status": "error", "message": "批次不存在"}), 404
    # 时间线：播种 -> 农事日志(施肥/打药等) -> 灌溉 -> 采收 -> 质检
    timeline = []
    if batch.get("sowing_date"):
        timeline.append({"date": batch["sowing_date"], "type": "sowing", "label": "播种", "desc": f"作物：{batch['crop_name']}"})
    for log in get_farm_logs():
        timeline.append({"date": log["created_at"][:10], "type": log["type"], "label": log["type"], "desc": log["description"]})
    if batch.get("harvest_date"):
        timeline.append({"date": batch["harvest_date"], "type": "harvest", "label": "采收", "desc": f"批次 {batch_no} 完成采收"})
    timeline.sort(key=lambda x: x["date"])
    return jsonify({"batch": batch, "timeline": timeline})


@app.route("/api/traceability/batches/<batch_no>/quality", methods=["POST"])
def api_batch_quality(batch_no):
    """更新批次质检状态。body: {quality_status: pending|qualified|unqualified}"""
    data = request.get_json(silent=True) or request.form
    update_batch_quality(batch_no, data.get("quality_status", "pending"))
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# 统计概览 API
# ---------------------------------------------------------------------------
@app.route("/api/stats/overview", methods=["GET"])
def api_stats_overview():
    """系统概览统计。"""
    return jsonify(get_overview_stats())


@app.route("/api/rules/evaluate", methods=["POST"])
def api_rules_evaluate():
    """手动触发规则引擎评估（调试用）。"""
    evaluate_rules()
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# 病害识别 API（模拟分类器，演示用）
# ---------------------------------------------------------------------------
# 常见作物病害库（用于模拟 AI 分类结果）
DISEASE_LIBRARY = [
    {"name": "番茄早疫病", "crop": "番茄", "symptom": "叶片出现同心轮纹状褐色病斑", "suggestion": "喷施百菌清或代森锰锌，及时摘除病叶"},
    {"name": "番茄晚疫病", "crop": "番茄", "symptom": "叶背出现白色霉层，病斑水渍状", "suggestion": "加强通风，喷施烯酰吗啉或霜霉威"},
    {"name": "黄瓜霜霉病", "crop": "黄瓜", "symptom": "叶片受叶脉限制的多角形黄色病斑", "suggestion": "控制棚内湿度，喷施吡唑醚菌酯"},
    {"name": "黄瓜白粉病", "crop": "黄瓜", "symptom": "叶面覆盖白色粉状霉层", "suggestion": "喷施三唑酮或醚菌酯，保持通风"},
    {"name": "辣椒炭疽病", "crop": "辣椒", "symptom": "果实出现凹陷褐色病斑，上有小黑点", "suggestion": "喷施咪鲜胺或苯醚甲环唑"},
    {"name": "草莓灰霉病", "crop": "草莓", "symptom": "花与果实出现灰色霉层并腐烂", "suggestion": "及时清除病果，喷施腐霉利或异菌脲"},
    {"name": "健康植株", "crop": "通用", "symptom": "未检测到明显病害特征", "suggestion": "继续保持当前田间管理措施"},
]


@app.route("/api/disease/detect", methods=["POST"])
def api_disease_detect():
    """
    病害识别接口（模拟）。
    接收上传图片，返回疑似病害类型 + 置信度 + 防治建议。
    实际生产环境可替换为训练好的 CNN/MobileNet 模型或调用云端 AI 服务。
    """
    # 基于文件名 + 大小做哈希，使同一图片结果稳定，不同图片有差异
    f = request.files.get("image")
    seed_str = ""
    if f:
        seed_str = f.filename + str(len(f.read() or b""))
    else:
        seed_str = request.form.get("filename", "unknown")
    h = int(hashlib.md5(seed_str.encode("utf-8")).hexdigest(), 16)
    rnd = random.Random(h)
    disease = rnd.choice(DISEASE_LIBRARY)
    confidence = round(rnd.uniform(0.72, 0.97), 3)
    return jsonify({
        "status": "ok",
        "disease": disease["name"],
        "crop": disease["crop"],
        "confidence": confidence,
        "symptom": disease["symptom"],
        "suggestion": disease["suggestion"],
        "mock": True,
    })


# ---------------------------------------------------------------------------
# 农业知识库 / 新闻 API
# ---------------------------------------------------------------------------
@app.route("/api/knowledge", methods=["GET"])
def api_knowledge_list():
    """知识库文章列表。query: category(可选)"""
    return jsonify(get_knowledge(request.args.get("category")))


@app.route("/api/knowledge/<int:article_id>", methods=["GET"])
def api_knowledge_detail(article_id):
    """知识库文章详情（自动累加阅读量）。"""
    article = get_knowledge_article(article_id)
    if not article:
        return jsonify({"status": "error", "message": "文章不存在"}), 404
    return jsonify(article)


@app.route("/api/news", methods=["GET"])
def api_news_list():
    """新闻列表。query: category(可选)"""
    return jsonify(get_news(request.args.get("category")))


@app.route("/api/news/<int:news_id>", methods=["GET"])
def api_news_detail(news_id):
    """新闻详情（自动累加阅读量）。"""
    article = get_news_article(news_id)
    if not article:
        return jsonify({"status": "error", "message": "新闻不存在"}), 404
    return jsonify(article)


# ---------------------------------------------------------------------------
# 客服留言 API
# ---------------------------------------------------------------------------
@app.route("/api/feedback", methods=["POST"])
def api_feedback_create():
    """提交客服留言。body: {name, contact, type, message}"""
    data = request.get_json(silent=True) or request.form
    if not data.get("message"):
        return jsonify({"status": "error", "message": "留言内容不能为空"}), 400
    insert_feedback(
        data.get("name", "匿名用户"),
        data.get("contact", ""),
        data.get("type", "产品咨询"),
        data["message"],
    )
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# 启动
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    init_db()

    # MQTT 连接必须在 app.run() 之前，且 use_reloader=False 避免线程重复启动
    # 使用 CallbackAPIVersion.VERSION1 兼容 paho-mqtt 2.x
    mqtt_client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION1)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_start()
    except Exception as e:
        # Mosquitto 未启动时不阻塞 Flask，便于前端联调 API
        print("MQTT connect failed (Flask still running):", e)

    # 启动规则引擎后台线程
    threading.Thread(target=_rule_engine_loop, daemon=True).start()
    print("Rule engine started (evaluates every 30s)")

    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False, use_reloader=False)
