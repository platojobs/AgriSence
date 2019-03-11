# -*- coding: utf-8 -*-
"""
AgriSense 后端主应用
- paho-mqtt 订阅传感器数据并入库
- Flask 提供 REST API 供前端查询与手动控制
"""

import json
import hashlib
import functools
import io
import csv
import random
import threading
import time
import uuid

from flask import Flask, request, jsonify, Response
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
    get_knowledge, get_knowledge_article, insert_knowledge,
    update_knowledge, delete_knowledge,
    get_news, get_news_article, insert_news,
    update_news, delete_news, toggle_news_top,
    insert_feedback, get_feedback_list, mark_feedback, delete_feedback,
    get_site_content, list_site_contents, upsert_site_content, delete_site_content,
    get_users, get_user, get_user_by_username, create_user, update_user, delete_user,
    touch_user_login, create_session, get_session, delete_session, clean_expired_sessions,
    insert_login_log, get_login_logs, update_user_password, delete_other_sessions,
    insert_audit_log, get_audit_logs, get_audit_stats,
    export_rows, export_count, EXPORT_TABLES,
    get_setting, set_setting, get_all_settings,
    insert_notification, notify_roles, get_notifications,
    mark_notification_read, mark_all_notifications_read,
    get_environment_daily, get_irrigation_stats, get_alert_stats,
    get_farm_activity_stats, get_batch_stats,
)
from irrigation_logic import decide
from weather_service import get_weather, rain_summary

app = Flask(__name__)
CORS(app)

# ---------------------------------------------------------------------------
# 系统设置：持久化到 settings 表，启动时加载（含默认值回填）
# ---------------------------------------------------------------------------
SETTING_DEFS = {
    "threshold_low":    {"label": "灌溉下限阈值(%)", "type": "float", "min": 0, "max": 100},
    "threshold_high":   {"label": "灌溉上限阈值(%)", "type": "float", "min": 0, "max": 100},
    "alert_cooldown":   {"label": "告警冷却时间(秒)", "type": "int",   "min": 60, "max": 86400},
    "site_name":        {"label": "站点名称",        "type": "str",   "max_len": 50},
    "refresh_interval": {"label": "前端轮询间隔(秒)", "type": "int",   "min": 2, "max": 300},
}
SETTING_DEFAULTS = {
    "threshold_low": DEFAULT_THRESHOLD_LOW,
    "threshold_high": DEFAULT_THRESHOLD_HIGH,
    "alert_cooldown": 600,
    "site_name": "AgriSense 智慧农业监测系统",
    "refresh_interval": 10,
}


def load_settings():
    """启动时从 settings 表加载配置；缺失项写入默认值并返回完整 dict。"""
    saved = get_all_settings()
    result = {}
    for key, default in SETTING_DEFAULTS.items():
        if key not in saved:
            set_setting(key, default)
            result[key] = default
        else:
            try:
                result[key] = float(saved[key]) if SETTING_DEFS[key]["type"] == "float" \
                    else int(saved[key]) if SETTING_DEFS[key]["type"] == "int" else saved[key]
            except (TypeError, ValueError):
                result[key] = default
    return result


# 灌溉阈值（持久化到 settings 表，启动时加载；可由前端 API 修改）
runtime_settings = None  # 启动时由 load_settings() 填充
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
    """根据最新读数、当前阈值与未来降水返回决策 dict。"""
    soil_moisture = latest.get("soil_moisture") if latest else None
    rain = rain_summary()
    action, reason = decide(
        soil_moisture,
        threshold_low=current_thresholds["low"],
        threshold_high=current_thresholds["high"],
        rain_prob=rain["rain_prob"],
        rain_mm=rain["rain_mm"],
    )
    return {
        "decision": action,
        "decision_text": reason,
        "threshold_low": current_thresholds["low"],
        "threshold_high": current_thresholds["high"],
        "rain_prob": rain["rain_prob"],
        "rain_mm": rain["rain_mm"],
    }


# ---------------------------------------------------------------------------
# 规则引擎：按告警规则评估最新读数，触发时自动生成告警
# ---------------------------------------------------------------------------
ALERT_COOLDOWN = 600  # 默认冷却时间(秒)；实际值取 settings 表 alert_cooldown
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

        # 冷却检查（冷却时间取系统设置 alert_cooldown）
        cooldown = ALERT_COOLDOWN
        if runtime_settings:
            try:
                cooldown = int(runtime_settings.get("alert_cooldown", ALERT_COOLDOWN))
            except (TypeError, ValueError):
                pass
        key = (metric, device_id)
        last_ts = _recent_alerts.get(key, 0)
        if now - last_ts < cooldown:
            continue

        cond_text = "低于" if rule["condition"] in ("lt", "<") else "高于"
        message = f"{metric} {cond_text} 阈值 {rule['threshold']}（当前值 {value}）"
        insert_alert(metric, rule.get("level", "warning"), message, device_id)
        _recent_alerts[key] = now
        # 同步生成站内通知，广播给管理员与操作员
        try:
            notify_roles(["admin", "operator"], "告警提醒", message, "alert")
        except Exception as e:
            print("notify error:", e)
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
# 用户认证与权限
# 角色：admin（管理员）> operator（操作员）> viewer（访客）
# ---------------------------------------------------------------------------
SESSION_TTL = 7 * 24 * 3600  # 会话有效期 7 天
ROLE_LEVEL = {"viewer": 1, "operator": 2, "admin": 3}
ROLE_LABELS = {"admin": "管理员", "operator": "操作员", "viewer": "访客"}


def hash_password(password, salt=None):
    """PBKDF2-HMAC-SHA256 加盐哈希，返回 (hash_hex, salt)。"""
    salt = salt or uuid.uuid4().hex[:16]
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000
    ).hex()
    return digest, salt


def _current_session():
    """从请求头 X-Auth-Token 解析当前会话。"""
    return get_session(request.headers.get("X-Auth-Token"))


def _audit(action, target=None, detail=None):
    """记录操作审计：自动取当前会话用户与请求 IP（未登录记 anonymous）。
    审计失败不影响主流程。"""
    session = _current_session()
    username = session["username"] if session else "anonymous"
    try:
        insert_audit_log(username, action, target, detail, request.remote_addr)
    except Exception as e:
        print("audit log error:", e)


def require_role(min_role="viewer"):
    """接口权限装饰器：要求登录且角色不低于 min_role。"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            session = _current_session()
            if not session:
                return jsonify({"status": "error", "message": "请先登录"}), 401
            if ROLE_LEVEL.get(session["role"], 0) < ROLE_LEVEL.get(min_role, 0):
                return jsonify({
                    "status": "error",
                    "message": "权限不足，需要%s及以上角色" % ROLE_LABELS.get(min_role, min_role),
                }), 403
            return func(*args, **kwargs)
        return wrapper
    return decorator


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    """登录。body: {"username": "...", "password": "..."}"""
    data = request.get_json(silent=True) or request.form
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"status": "error", "message": "用户名和密码不能为空"}), 400

    user = get_user_by_username(username)
    if not user:
        insert_login_log(username, request.remote_addr, request.headers.get("User-Agent", ""), False)
        return jsonify({"status": "error", "message": "用户名或密码错误"}), 401
    if user.get("status") != "active":
        insert_login_log(username, request.remote_addr, request.headers.get("User-Agent", ""), False)
        return jsonify({"status": "error", "message": "该账号已被禁用，请联系管理员"}), 403

    digest, _ = hash_password(password, user["salt"])
    if digest != user["password_hash"]:
        insert_login_log(username, request.remote_addr, request.headers.get("User-Agent", ""), False)
        return jsonify({"status": "error", "message": "用户名或密码错误"}), 401

    token = uuid.uuid4().hex
    expires_at = int(time.time()) + SESSION_TTL
    create_session(token, username, user["role"], expires_at)
    touch_user_login(username)
    insert_login_log(username, request.remote_addr, request.headers.get("User-Agent", ""), True)
    clean_expired_sessions()

    return jsonify({
        "status": "ok",
        "token": token,
        "expires_at": expires_at,
        "user": {
            "username": user["username"],
            "display_name": user["display_name"],
            "role": user["role"],
            "role_label": ROLE_LABELS.get(user["role"], user["role"]),
        },
    })


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    """退出登录。"""
    delete_session(request.headers.get("X-Auth-Token"))
    return jsonify({"status": "ok"})


@app.route("/api/auth/me", methods=["GET"])
def api_me():
    """当前登录用户。"""
    session = _current_session()
    if not session:
        return jsonify({"status": "error", "message": "未登录"}), 401
    user = get_user_by_username(session["username"])
    if not user:
        return jsonify({"status": "error", "message": "用户不存在"}), 401
    user.pop("password_hash", None)
    user.pop("salt", None)
    user["role_label"] = ROLE_LABELS.get(user["role"], user["role"])
    return jsonify({"status": "ok", "user": user})


@app.route("/api/auth/change_password", methods=["POST"])
def api_change_password():
    """用户本人修改密码。body: {"old_password", "new_password"}"""
    session = _current_session()
    if not session:
        return jsonify({"status": "error", "message": "请先登录"}), 401

    data = request.get_json(silent=True) or request.form
    old_password = data.get("old_password") or ""
    new_password = data.get("new_password") or ""

    if len(new_password) < 6:
        return jsonify({"status": "error", "message": "新密码至少 6 个字符"}), 400

    user = get_user_by_username(session["username"])
    if not user:
        return jsonify({"status": "error", "message": "用户不存在"}), 401

    digest, _ = hash_password(old_password, user["salt"])
    if digest != user["password_hash"]:
        return jsonify({"status": "error", "message": "原密码不正确"}), 400

    new_hash, new_salt = hash_password(new_password)
    update_user_password(session["username"], new_hash, new_salt)
    _audit("change_password", target=session["username"], detail="本人修改密码")
    return jsonify({"status": "ok", "message": "密码修改成功"})


@app.route("/api/auth/login_history", methods=["GET"])
def api_login_history():
    """当前用户最近 20 条登录记录。"""
    session = _current_session()
    if not session:
        return jsonify({"status": "error", "message": "请先登录"}), 401
    logs = get_login_logs(session["username"], limit=20)
    for log in logs:
        log["success"] = bool(log["success"])
    return jsonify({"status": "ok", "logs": logs})


@app.route("/api/auth/logout_others", methods=["POST"])
def api_logout_others():
    """退出当前用户的其他所有会话（保留当前 token）。"""
    session = _current_session()
    if not session:
        return jsonify({"status": "error", "message": "请先登录"}), 401
    removed = delete_other_sessions(session["username"], session["token"])
    _audit("logout_others", target=session["username"], detail="退出 %d 个会话" % removed)
    return jsonify({"status": "ok", "removed": removed})


# ---------------------------------------------------------------------------
# 操作审计 API（仅管理员）
# ---------------------------------------------------------------------------
@app.route("/api/audit_logs", methods=["GET"])
@require_role("admin")
def api_audit_logs():
    """审计日志查询。query: username/action/keyword/limit"""
    username = request.args.get("username") or None
    action = request.args.get("action") or None
    keyword = request.args.get("keyword") or None
    try:
        limit = min(int(request.args.get("limit", 100)), 500)
    except (TypeError, ValueError):
        limit = 100
    logs = get_audit_logs(limit=limit, username=username, action=action, keyword=keyword)
    stats = get_audit_stats()
    return jsonify({"status": "ok", "logs": logs, "stats": stats})


# ---------------------------------------------------------------------------
# 数据导出中心 API（CSV 下载）
# 业务数据 operator 及以上可导；audit_logs 仅 admin
# ---------------------------------------------------------------------------
EXPORT_META = {
    "sensor_readings": {"label": "环境监测数据", "min_role": "operator"},
    "irrigation_logs": {"label": "灌溉操作日志", "min_role": "operator"},
    "alerts": {"label": "告警记录", "min_role": "operator"},
    "farm_logs": {"label": "农事日志", "min_role": "operator"},
    "traceability_batches": {"label": "溯源批次", "min_role": "operator"},
    "audit_logs": {"label": "操作审计日志", "min_role": "admin"},
}


@app.route("/api/export/types", methods=["GET"])
@require_role("operator")
def api_export_types():
    """列出当前角色可导出的数据类型及数据量。"""
    session = _current_session()
    level = ROLE_LEVEL.get(session["role"], 0)
    types = []
    for key, meta in EXPORT_META.items():
        if level < ROLE_LEVEL.get(meta["min_role"], 99):
            continue
        types.append({
            "type": key,
            "label": meta["label"],
            "min_role": meta["min_role"],
            "count": export_count(key),
        })
    return jsonify({"status": "ok", "types": types})


@app.route("/api/export/<data_type>", methods=["GET"])
@require_role("operator")
def api_export_csv(data_type):
    """导出 CSV。query: start_date/end_date (YYYY-MM-DD), limit"""
    meta = EXPORT_META.get(data_type)
    if not meta or data_type not in EXPORT_TABLES:
        return jsonify({"status": "error", "message": "不支持的数据类型"}), 400

    session = _current_session()
    if ROLE_LEVEL.get(session["role"], 0) < ROLE_LEVEL.get(meta["min_role"], 99):
        return jsonify({
            "status": "error",
            "message": "权限不足，导出%s需要%s角色" % (meta["label"], ROLE_LABELS.get(meta["min_role"])),
        }), 403

    start_date = request.args.get("start_date") or None
    end_date = request.args.get("end_date") or None
    try:
        limit = min(int(request.args.get("limit", 10000)), 50000)
    except (TypeError, ValueError):
        limit = 10000

    columns, rows = export_rows(data_type, start_date=start_date, end_date=end_date, limit=limit)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(columns)
    writer.writerows(rows)
    # utf-8-sig：带 BOM，保证 Excel 打开中文不乱码
    csv_data = "\ufeff" + buf.getvalue()

    filename = "%s_%s.csv" % (data_type, time.strftime("%Y%m%d_%H%M%S"))
    _audit("export", target=data_type,
           detail="导出 %s %d 条（%s ~ %s）" % (meta["label"], len(rows), start_date or "最早", end_date or "最新"))

    return Response(
        csv_data.encode("utf-8"),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=%s" % filename},
    )


# ---------------------------------------------------------------------------
# 用户管理 API（仅管理员）
# ---------------------------------------------------------------------------
@app.route("/api/users", methods=["GET"])
@require_role("admin")
def api_users_list():
    """用户列表。"""
    users = get_users()
    for u in users:
        u["role_label"] = ROLE_LABELS.get(u["role"], u["role"])
    return jsonify(users)


@app.route("/api/users", methods=["POST"])
@require_role("admin")
def api_user_create():
    """新增用户。body: {"username","password","display_name","role"}"""
    data = request.get_json(silent=True) or request.form
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    role = data.get("role") or "viewer"

    if not username or len(username) < 3:
        return jsonify({"status": "error", "message": "用户名至少 3 个字符"}), 400
    if len(password) < 6:
        return jsonify({"status": "error", "message": "密码至少 6 个字符"}), 400
    if role not in ROLE_LEVEL:
        return jsonify({"status": "error", "message": "角色不合法"}), 400
    if get_user_by_username(username):
        return jsonify({"status": "error", "message": "用户名已存在"}), 400

    digest, salt = hash_password(password)
    user_id = create_user(username, digest, salt, data.get("display_name") or username, role)
    _audit("user_create", target=username, detail="创建用户，角色 %s" % role)
    return jsonify({"status": "ok", "id": user_id})


@app.route("/api/users/<int:user_id>", methods=["PUT"])
@require_role("admin")
def api_user_update(user_id):
    """修改用户角色 / 状态 / 姓名 / 密码。"""
    session = _current_session()
    target = get_user(user_id)
    if not target:
        return jsonify({"status": "error", "message": "用户不存在"}), 404

    data = request.get_json(silent=True) or request.form
    role = data.get("role")
    status = data.get("status")
    display_name = data.get("display_name")
    password = data.get("password")

    if role is not None and role not in ROLE_LEVEL:
        return jsonify({"status": "error", "message": "角色不合法"}), 400
    if status is not None and status not in ("active", "disabled"):
        return jsonify({"status": "error", "message": "状态不合法"}), 400
    # 防止管理员把自己降级或禁用
    if target["username"] == session["username"]:
        if role is not None and role != "admin":
            return jsonify({"status": "error", "message": "不能修改自己的管理员角色"}), 400
        if status == "disabled":
            return jsonify({"status": "error", "message": "不能禁用自己的账号"}), 400

    password_hash = salt = None
    if password:
        if len(password) < 6:
            return jsonify({"status": "error", "message": "密码至少 6 个字符"}), 400
        password_hash, salt = hash_password(password)

    update_user(user_id, role=role, status=status, display_name=display_name,
                password_hash=password_hash, salt=salt)
    changes = []
    if role is not None:
        changes.append("角色→" + role)
    if status is not None:
        changes.append("状态→" + status)
    if display_name is not None:
        changes.append("姓名→" + display_name)
    if password:
        changes.append("重置密码")
    _audit("user_update", target=target["username"], detail="、".join(changes) or "无变更")
    return jsonify({"status": "ok"})


@app.route("/api/users/<int:user_id>", methods=["DELETE"])
@require_role("admin")
def api_user_delete(user_id):
    """删除用户。"""
    session = _current_session()
    target = get_user(user_id)
    if not target:
        return jsonify({"status": "error", "message": "用户不存在"}), 404
    if target["username"] == session["username"]:
        return jsonify({"status": "error", "message": "不能删除自己的账号"}), 400

    admin_count = len([u for u in get_users()
                       if u["role"] == "admin" and u["status"] == "active"])
    if target["role"] == "admin" and admin_count <= 1:
        return jsonify({"status": "error", "message": "至少需要保留一个可用管理员"}), 400

    delete_user(user_id)
    _audit("user_delete", target=target["username"], detail="删除用户")
    return jsonify({"status": "ok"})


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
    _audit("irrigation_manual", target="irrigation_valve", detail=reason)
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
    # 持久化到系统设置，重启后仍生效
    set_setting("threshold_low", low)
    set_setting("threshold_high", high)
    if runtime_settings is not None:
        runtime_settings["threshold_low"] = low
        runtime_settings["threshold_high"] = high
    _audit("thresholds_update", target="irrigation", detail="阈值 %s ~ %s" % (low, high))
    return jsonify({"status": "ok", "low": low, "high": high})


# ---------------------------------------------------------------------------
# 系统设置 API（仅管理员）
# ---------------------------------------------------------------------------
@app.route("/api/settings", methods=["GET"])
@require_role("admin")
def api_settings_get():
    """返回全部系统设置项及元数据。"""
    saved = get_all_settings()
    items = []
    for key, meta in SETTING_DEFS.items():
        value = saved.get(key, SETTING_DEFAULTS.get(key))
        items.append({"key": key, "value": value, "label": meta["label"], "type": meta["type"]})
    return jsonify({"status": "ok", "settings": items})


@app.route("/api/settings", methods=["PUT"])
@require_role("admin")
def api_settings_put():
    """批量更新系统设置。body: {"settings": {"key": value, ...}}"""
    data = request.get_json(silent=True) or {}
    updates = data.get("settings") or {}
    if not isinstance(updates, dict) or not updates:
        return jsonify({"status": "error", "message": "没有需要更新的设置"}), 400

    applied = {}
    for key, value in updates.items():
        meta = SETTING_DEFS.get(key)
        if not meta:
            return jsonify({"status": "error", "message": "未知设置项：%s" % key}), 400
        try:
            if meta["type"] == "float":
                value = float(value)
            elif meta["type"] == "int":
                value = int(float(value))
            else:
                value = str(value).strip()
                if not value or len(value) > meta.get("max_len", 200):
                    raise ValueError("长度不合法")
        except (TypeError, ValueError):
            return jsonify({"status": "error", "message": "%s 取值不合法" % meta["label"]}), 400
        if meta["type"] in ("float", "int"):
            if value < meta.get("min", -1e18) or value > meta.get("max", 1e18):
                return jsonify({"status": "error", "message": "%s 超出允许范围" % meta["label"]}), 400
        applied[key] = value

    # 阈值特殊校验：下限必须小于上限
    low = applied.get("threshold_low", current_thresholds["low"])
    high = applied.get("threshold_high", current_thresholds["high"])
    if float(low) >= float(high):
        return jsonify({"status": "error", "message": "灌溉下限必须小于上限"}), 400

    for key, value in applied.items():
        set_setting(key, value)
    if runtime_settings is not None:
        runtime_settings.update(applied)
    current_thresholds["low"] = float(low)
    current_thresholds["high"] = float(high)

    detail = "、".join("%s=%s" % (SETTING_DEFS[k]["label"], v) for k, v in applied.items())
    _audit("settings_update", target="settings", detail=detail)
    return jsonify({"status": "ok", "settings": applied})


# ---------------------------------------------------------------------------
# 站内通知 API（登录用户均可访问自己的通知）
# ---------------------------------------------------------------------------
@app.route("/api/notifications", methods=["GET"])
@require_role("viewer")
def api_notifications():
    """我的通知列表 + 未读数。query: limit, unread=1"""
    session = _current_session()
    try:
        limit = min(int(request.args.get("limit", 20)), 200)
    except (TypeError, ValueError):
        limit = 20
    unread_only = request.args.get("unread") == "1"
    items, unread = get_notifications(session["username"], limit=limit, unread_only=unread_only)
    return jsonify({"status": "ok", "notifications": items, "unread": unread})


@app.route("/api/notifications/<int:nid>/read", methods=["POST"])
@require_role("viewer")
def api_notification_read(nid):
    """标记一条通知已读（仅本人）。"""
    session = _current_session()
    ok = mark_notification_read(nid, session["username"])
    if not ok:
        return jsonify({"status": "error", "message": "通知不存在"}), 404
    return jsonify({"status": "ok"})


@app.route("/api/notifications/read_all", methods=["POST"])
@require_role("viewer")
def api_notifications_read_all():
    """我的通知全部标记已读。"""
    session = _current_session()
    n = mark_all_notifications_read(session["username"])
    return jsonify({"status": "ok", "marked": n})


# ---------------------------------------------------------------------------
# 气象服务 API
# ---------------------------------------------------------------------------
@app.route("/api/weather", methods=["GET"])
def api_weather():
    """城市气象：当前天气 + 24 小时 + 7 天预报 + 农事指数 + 天气驱动灌溉建议。"""
    city = request.args.get("city", default="杭州", type=str)
    weather = get_weather(city)

    latest = get_latest()
    decision = _build_decision(latest)

    # 天气联动的灌溉建议：把墒情决策与未来降水合并给出结论
    if decision["decision"] == "hold" and decision["rain_prob"] >= 60:
        tip = "系统已根据降雨预报自动推迟灌溉，预计可节省 1 次灌溉用水"
    elif decision["decision"] == "start":
        tip = "未来 24 小时降水不足以补充墒情，建议按计划灌溉"
    elif decision["decision"] == "stop":
        tip = "墒情充足，无需灌溉，注意排水防涝"
    else:
        tip = "墒情与气象条件均正常，无需灌溉"

    weather["irrigation"] = {
        "soil_moisture": latest.get("soil_moisture") if latest else None,
        "decision": decision["decision"],
        "decision_text": decision["decision_text"],
        "rain_prob": decision["rain_prob"],
        "rain_mm": decision["rain_mm"],
        "threshold_low": decision["threshold_low"],
        "threshold_high": decision["threshold_high"],
        "tip": tip,
    }
    return jsonify(weather)


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
    _audit("device_upsert", target=device_id, detail="保存设备「%s」" % data.get("name", device_id))
    return jsonify({"status": "ok"})


@app.route("/api/devices/<device_id>", methods=["DELETE"])
def api_device_delete(device_id):
    """删除设备。"""
    delete_device(device_id)
    _audit("device_delete", target=device_id, detail="删除设备")
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
    _audit("alert_handle", target="alert#%d" % alert_id, detail="标记告警已处理")
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
        _audit("alert_rule_save", target=str(data.get("metric")),
               detail="%s %s %s（%s）" % (data.get("metric"), data.get("condition"),
                                          data.get("threshold"), data.get("level", "warning")))
        return jsonify({"status": "ok"})
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "参数错误"}), 400


@app.route("/api/alert-rules/<int:rule_id>", methods=["DELETE"])
def api_alert_rule_delete(rule_id):
    """删除告警规则。"""
    delete_alert_rule(rule_id)
    _audit("alert_rule_delete", target="rule#%d" % rule_id, detail="删除告警规则")
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
    _audit("schedule_create", target=data.get("name", "定时灌溉"),
           detail="%s 起 %s 分钟" % (data.get("start_time", "06:00"), data.get("duration", 30)))
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
    _audit("schedule_update", target="schedule#%d" % schedule_id,
           detail="%s %s 起 %s 分钟" % (data.get("name", "定时灌溉"),
                                       data.get("start_time", "06:00"), data.get("duration", 30)))
    return jsonify({"status": "ok"})


@app.route("/api/irrigation/schedules/<int:schedule_id>", methods=["DELETE"])
def api_schedule_delete(schedule_id):
    """删除灌溉调度。"""
    delete_schedule(schedule_id)
    _audit("schedule_delete", target="schedule#%d" % schedule_id, detail="删除灌溉调度")
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
    _audit("actuator_control", target=name, detail="切换为 %s" % status)
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
    _audit("farm_log_create", target=data.get("type", "其他"),
           detail=(data.get("description") or "")[:80])
    return jsonify({"status": "ok"})


@app.route("/api/farm-logs/<int:log_id>", methods=["DELETE"])
def api_farm_log_delete(log_id):
    """删除农事日志。"""
    delete_farm_log(log_id)
    _audit("farm_log_delete", target="farm_log#%d" % log_id, detail="删除农事日志")
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
    _audit("batch_create", target=data["batch_no"], detail="创建批次「%s」" % data.get("crop_name", ""))
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
    _audit("batch_quality", target=batch_no, detail="质检状态→%s" % data.get("quality_status", "pending"))
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# 统计概览 API
# ---------------------------------------------------------------------------
@app.route("/api/stats/overview", methods=["GET"])
def api_stats_overview():
    """系统概览统计。"""
    return jsonify(get_overview_stats())


# ---------------------------------------------------------------------------
# 统计报表 API（操作员及以上可访问）
# ---------------------------------------------------------------------------
def _parse_days():
    raw = request.args.get("days", "7")
    try:
        d = int(raw)
        if d < 1: d = 1
        if d > 365: d = 365
    except Exception:
        d = 7
    return d


@app.route("/api/reports/dashboard", methods=["GET"])
@require_role("operator")
def api_reports_dashboard():
    """综合统计卡片：近 N 天读数总量、平均墒情、平均温度、灌溉次数、告警数、批次。"""
    days = _parse_days()
    stats = get_overview_stats(hours=days * 24)
    env = get_environment_daily(days=days)
    # 平均墒情取时间序列的平均（跳过 None）
    moist_vals = [v for v in env["avg_moisture"] if v is not None]
    temp_vals = [v for v in env["avg_temp"] if v is not None]
    avg_moisture = round(sum(moist_vals) / len(moist_vals), 1) if moist_vals else None
    avg_temp = round(sum(temp_vals) / len(temp_vals), 1) if temp_vals else None
    irr = get_irrigation_stats(days=days)
    alerts = get_alert_stats(days=days)
    batches = get_batch_stats()
    return jsonify({
        "reading_count": stats["reading_count"],
        "device_count": stats["device_count"],
        "avg_moisture": avg_moisture,
        "avg_temperature": avg_temp,
        "irrigation_start": irr["total_start"],
        "irrigation_stop": irr["total_stop"],
        "alert_total": alerts["total"],
        "batch_count": sum([b["value"] for b in batches["status_distribution"]]),
        "days": days,
    })


@app.route("/api/reports/environment", methods=["GET"])
@require_role("operator")
def api_reports_environment():
    """按天环境指标均值 / 极值。"""
    return jsonify(get_environment_daily(days=_parse_days()))


@app.route("/api/reports/irrigation", methods=["GET"])
@require_role("operator")
def api_reports_irrigation():
    """灌溉次数按天分布 + 最近 30 条日志。"""
    return jsonify(get_irrigation_stats(days=_parse_days()))


@app.route("/api/reports/alerts", methods=["GET"])
@require_role("operator")
def api_reports_alerts():
    """告警等级分布 + 类型分布 + 按天趋势。"""
    return jsonify(get_alert_stats(days=_parse_days()))


@app.route("/api/reports/farm", methods=["GET"])
@require_role("operator")
def api_reports_farm():
    """农事活动类型分布。"""
    return jsonify(get_farm_activity_stats())


@app.route("/api/reports/batch", methods=["GET"])
@require_role("operator")
def api_reports_batch():
    """溯源批次质量状态分布 + 作物类型分布。"""
    return jsonify(get_batch_stats())


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
# CMS 后台接口（管理员专属）
# ---------------------------------------------------------------------------

# ---- 知识库 ----

@app.route("/api/cms/knowledge", methods=["GET"])
@require_role("admin")
def api_cms_knowledge_list():
    """知识库管理列表（含全文，默认 200 条）。"""
    return jsonify(get_knowledge(limit=200))


@app.route("/api/cms/knowledge", methods=["POST"])
@require_role("admin")
def api_cms_knowledge_create():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    content = data.get("content", "").strip()
    if not title or not content:
        return jsonify({"status": "error", "message": "标题与正文不能为空"}), 400
    insert_knowledge(
        data.get("category", "种植技术"),
        title,
        data.get("summary", content[:80]),
        content,
        data.get("author", "农技专家"),
    )
    _audit("cms_knowledge_create", target=title, detail="新增知识文章")
    return jsonify({"status": "ok"})


@app.route("/api/cms/knowledge/<int:article_id>", methods=["PUT"])
@require_role("admin")
def api_cms_knowledge_update(article_id):
    data = request.get_json(silent=True) or {}
    row = update_knowledge(
        article_id,
        category=data.get("category"),
        title=data.get("title"),
        summary=data.get("summary"),
        content=data.get("content"),
        author=data.get("author"),
    )
    _audit("cms_knowledge_update", target="knowledge#%d" % article_id,
           detail="更新知识文章「%s」" % (data.get("title") or ""))
    return jsonify({"status": "ok", "article": row})


@app.route("/api/cms/knowledge/<int:article_id>", methods=["DELETE"])
@require_role("admin")
def api_cms_knowledge_delete(article_id):
    delete_knowledge(article_id)
    _audit("cms_knowledge_delete", target="knowledge#%d" % article_id, detail="删除知识文章")
    return jsonify({"status": "ok"})


# ---- 新闻 ----

@app.route("/api/cms/news", methods=["GET"])
@require_role("admin")
def api_cms_news_list():
    return jsonify(get_news(limit=200))


@app.route("/api/cms/news", methods=["POST"])
@require_role("admin")
def api_cms_news_create():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    content = data.get("content", "").strip()
    if not title or not content:
        return jsonify({"status": "error", "message": "标题与正文不能为空"}), 400
    insert_news(
        data.get("category", "行业动态"),
        title,
        data.get("summary", content[:80]),
        content,
        data.get("source", "AgriSense 资讯"),
        1 if data.get("is_top") else 0,
    )
    _audit("cms_news_create", target=title, detail="新增新闻")
    return jsonify({"status": "ok"})


@app.route("/api/cms/news/<int:news_id>", methods=["PUT"])
@require_role("admin")
def api_cms_news_update(news_id):
    data = request.get_json(silent=True) or {}
    is_top = None
    if "is_top" in data:
        is_top = 1 if data.get("is_top") else 0
    row = update_news(
        news_id,
        category=data.get("category"),
        title=data.get("title"),
        summary=data.get("summary"),
        content=data.get("content"),
        source=data.get("source"),
        is_top=is_top,
    )
    _audit("cms_news_update", target="news#%d" % news_id,
           detail="更新新闻「%s」" % (data.get("title") or ""))
    return jsonify({"status": "ok", "news": row})


@app.route("/api/cms/news/<int:news_id>", methods=["DELETE"])
@require_role("admin")
def api_cms_news_delete(news_id):
    delete_news(news_id)
    _audit("cms_news_delete", target="news#%d" % news_id, detail="删除新闻")
    return jsonify({"status": "ok"})


@app.route("/api/cms/news/<int:news_id>/top", methods=["POST"])
@require_role("admin")
def api_cms_news_toggle_top(news_id):
    data = request.get_json(silent=True) or {}
    toggle_news_top(news_id, bool(data.get("is_top")))
    _audit("cms_news_top", target="news#%d" % news_id,
           detail="置顶" if data.get("is_top") else "取消置顶")
    return jsonify({"status": "ok"})


# ---- 客服留言管理 ----

@app.route("/api/cms/feedback", methods=["GET"])
@require_role("admin")
def api_cms_feedback_list():
    status = request.args.get("status")
    return jsonify(get_feedback_list(status=status))


@app.route("/api/cms/feedback/<int:fb_id>/mark", methods=["POST"])
@require_role("admin")
def api_cms_feedback_mark(fb_id):
    data = request.get_json(silent=True) or {}
    mark_feedback(
        fb_id,
        data.get("status", "resolved"),
        reply=data.get("reply"),
    )
    _audit("cms_feedback_mark", target="feedback#%d" % fb_id,
           detail="留言状态→%s" % data.get("status", "resolved"))
    return jsonify({"status": "ok"})


@app.route("/api/cms/feedback/<int:fb_id>", methods=["DELETE"])
@require_role("admin")
def api_cms_feedback_delete(fb_id):
    delete_feedback(fb_id)
    _audit("cms_feedback_delete", target="feedback#%d" % fb_id, detail="删除留言")
    return jsonify({"status": "ok"})


# ---- 站点内容管理（FAQ / 关于 / 隐私 / 服务条款） ----

@app.route("/api/cms/site", methods=["GET"])
@require_role("admin")
def api_cms_site_list():
    """返回所有可编辑站点内容条目。"""
    return jsonify(list_site_contents())


@app.route("/api/cms/site/<key>", methods=["GET"])
def api_site_public_get(key):
    """公开：站点内容条目（访客也能读，供 about/faq/privacy 页面用）。"""
    row = get_site_content(key)
    if row is None:
        # 返回占位，让前端无数据时也能渲染默认
        return jsonify({"key": key, "title": "", "content": ""})
    return jsonify(row)


@app.route("/api/cms/site/<key>", methods=["PUT"])
@require_role("admin")
def api_cms_site_upsert(key):
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    content = data.get("content", "").strip()
    if not title or not content:
        return jsonify({"status": "error", "message": "标题与正文不能为空"}), 400
    upsert_site_content(key, title, content)
    _audit("cms_site_save", target=key, detail="保存站点内容「%s」" % title)
    return jsonify({"status": "ok"})


@app.route("/api/cms/site/<key>", methods=["DELETE"])
@require_role("admin")
def api_cms_site_delete(key):
    delete_site_content(key)
    _audit("cms_site_delete", target=key, detail="删除站点内容")
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# 启动
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    init_db()

    # 加载持久化系统设置（缺失项自动写入默认值），并同步灌溉阈值
    runtime_settings = load_settings()
    current_thresholds["low"] = float(runtime_settings["threshold_low"])
    current_thresholds["high"] = float(runtime_settings["threshold_high"])
    print("Settings loaded:", runtime_settings)

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
