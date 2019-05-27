# -*- coding: utf-8 -*-
"""
AgriSense 数据库操作层
- 使用 sqlite3，每次操作都通过 with sqlite3.connect(...) as conn
- conn.row_factory = sqlite3.Row，便于按字段名取值
"""

import os
import sqlite3
import time
import datetime

from config import DATABASE_PATH


def _get_conn():
    """获取数据库连接（相对 app.py 所在目录解析路径）。"""
    # DATABASE_PATH 是相对于 backend 目录的路径
    db_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(db_dir, DATABASE_PATH)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """创建数据表（如不存在）。"""
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sensor_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT,
                soil_moisture REAL,
                temperature REAL,
                humidity REAL,
                light INTEGER,
                raw INTEGER,
                timestamp INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS irrigation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT,
                reason TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 设备表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT UNIQUE,
                name TEXT,
                location TEXT,
                status TEXT DEFAULT 'offline',
                last_seen INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 告警表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT,
                level TEXT DEFAULT 'warning',
                message TEXT,
                device_id TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                handled_at TEXT
            )
        """)
        # 告警规则表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alert_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric TEXT,
                condition TEXT,
                threshold REAL,
                level TEXT DEFAULT 'warning',
                enabled INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 告警规则命中明细表：用于规则命中趋势图表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rule_hits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id INTEGER,
                metric TEXT,
                level TEXT DEFAULT 'warning',
                device_id TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 灌溉调度表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS irrigation_schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                start_time TEXT,
                duration INTEGER,
                enabled INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 执行器表（水泵/肥泵/风机/遮阳网等）
        conn.execute("""
            CREATE TABLE IF NOT EXISTS actuators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                label TEXT,
                status TEXT DEFAULT 'off',
                device_id TEXT,
                last_changed TEXT DEFAULT CURRENT_TIMESTAMP,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 农事日志表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS farm_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT,
                description TEXT,
                operator TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 溯源批次表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS traceability_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_no TEXT UNIQUE,
                crop_name TEXT,
                sowing_date TEXT,
                harvest_date TEXT,
                quality_status TEXT DEFAULT 'pending',
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 农业知识库表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                title TEXT,
                summary TEXT,
                content TEXT,
                author TEXT,
                views INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 农业新闻表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS news_articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                title TEXT,
                summary TEXT,
                content TEXT,
                source TEXT,
                is_top INTEGER DEFAULT 0,
                views INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 客服留言表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                contact TEXT,
                type TEXT,
                message TEXT,
                status TEXT DEFAULT 'pending',
                reply TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 站点内容表：FAQ、关于我们、隐私政策、服务条款等
        conn.execute("""
            CREATE TABLE IF NOT EXISTS site_contents (
                key TEXT PRIMARY KEY,
                title TEXT,
                content TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 用户表：角色 admin（管理员）/ operator（操作员）/ viewer（访客）
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                display_name TEXT,
                role TEXT DEFAULT 'viewer',
                status TEXT DEFAULT 'active',
                last_login TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 登录会话表：前端用 X-Auth-Token 携带
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                role TEXT NOT NULL,
                expires_at INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 登录日志表：记录每次登录尝试（成功与失败）
        conn.execute("""
            CREATE TABLE IF NOT EXISTS login_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                ip TEXT,
                user_agent TEXT,
                success INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 操作审计表：记录后台关键变更操作（谁、做了什么、操作对象）
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                action TEXT,
                target TEXT,
                detail TEXT,
                ip TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 系统设置表：灌溉阈值、告警冷却、站点参数等持久化配置
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 站内通知表：按用户投递（告警广播到 admin/operator，个人事件仅本人）
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                title TEXT,
                content TEXT,
                type TEXT DEFAULT 'info',
                is_read INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 工单表：告警/日常运维工单，支持指派、流转与处理记录
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_no TEXT UNIQUE,
                title TEXT NOT NULL,
                description TEXT,
                type TEXT DEFAULT 'ops',
                priority TEXT DEFAULT 'medium',
                status TEXT DEFAULT 'open',
                alert_id INTEGER,
                creator TEXT,
                assignee TEXT,
                resolution TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT,
                closed_at TEXT
            )
        """)
        # 数据维护日志表：记录手动/自动清理与 VACUUM 操作
        conn.execute("""
            CREATE TABLE IF NOT EXISTS maintenance_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT,
                target_table TEXT,
                removed_rows INTEGER DEFAULT 0,
                retention_days INTEGER,
                mode TEXT DEFAULT 'manual',
                operator TEXT,
                detail TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 固件版本表：OTA 固件包元数据（文件存于 firmware_store/ 目录）
        conn.execute("""
            CREATE TABLE IF NOT EXISTS firmware_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version TEXT NOT NULL,
                device_model TEXT NOT NULL,
                filename TEXT,
                stored_name TEXT,
                size INTEGER DEFAULT 0,
                checksum TEXT,
                changelog TEXT,
                is_latest INTEGER DEFAULT 0,
                downloads INTEGER DEFAULT 0,
                uploaded_by TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(version, device_model)
            )
        """)
        # 设备分组表：按大棚/地块归组，便于分区管理与统计
        conn.execute("""
            CREATE TABLE IF NOT EXISTS device_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                location TEXT,
                description TEXT,
                leader TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # devices 表补充 group_id 列（兼容旧库，无需重建表）
        device_cols = [r["name"] for r in conn.execute("PRAGMA table_info(devices)").fetchall()]
        if "group_id" not in device_cols:
            conn.execute("ALTER TABLE devices ADD COLUMN group_id INTEGER")
        # alert_rules 表补充命中统计列（命中次数 / 最近触发时间）
        rule_cols = [r["name"] for r in conn.execute("PRAGMA table_info(alert_rules)").fetchall()]
        if "trigger_count" not in rule_cols:
            conn.execute("ALTER TABLE alert_rules ADD COLUMN trigger_count INTEGER DEFAULT 0")
        if "last_triggered_at" not in rule_cols:
            conn.execute("ALTER TABLE alert_rules ADD COLUMN last_triggered_at TEXT")
        # sensor_readings 表补充数据来源列（sensor=真实上报 / mock=模拟生成）
        reading_cols = [r["name"] for r in conn.execute("PRAGMA table_info(sensor_readings)").fetchall()]
        if "source" not in reading_cols:
            conn.execute("ALTER TABLE sensor_readings ADD COLUMN source TEXT DEFAULT 'sensor'")
        conn.commit()


def insert_reading(device_id, soil_moisture, raw, timestamp,
                   temperature=None, humidity=None, light=None, source="sensor"):
    """插入一条传感器读数（温湿度光照可选）。"""
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO sensor_readings (device_id, soil_moisture, temperature, humidity, light, raw, timestamp, source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (device_id, soil_moisture, temperature, humidity, light, raw, timestamp, source)
        )
        conn.commit()


def insert_readings_bulk(rows):
    """批量插入读数，rows 每项为
    (device_id, soil_moisture, raw, timestamp, temperature, humidity, light, source)。"""
    with _get_conn() as conn:
        conn.executemany(
            "INSERT INTO sensor_readings (device_id, soil_moisture, raw, timestamp, "
            "temperature, humidity, light, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    return len(rows)


def get_mock_stats():
    """模拟数据统计：总数、模拟行数、模拟数据时间范围。"""
    with _get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM sensor_readings").fetchone()["c"]
        mock = conn.execute(
            "SELECT COUNT(*) AS c FROM sensor_readings WHERE source = 'mock'"
        ).fetchone()["c"]
        row = conn.execute(
            "SELECT MIN(timestamp) AS earliest, MAX(timestamp) AS latest "
            "FROM sensor_readings WHERE source = 'mock'"
        ).fetchone()
    return {"total": total, "mock": mock,
            "earliest": row["earliest"], "latest": row["latest"]}


def delete_mock_readings():
    """删除全部模拟生成读数，返回删除条数。"""
    with _get_conn() as conn:
        cur = conn.execute("DELETE FROM sensor_readings WHERE source = 'mock'")
        conn.commit()
    return cur.rowcount


def get_latest():
    """返回最新一条读数 dict，无数据返回 None。"""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM sensor_readings ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return dict(row)


def get_recent_readings(limit=20):
    """返回最近 N 条传感器读数 list[dict]（按 id 倒序）。"""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM sensor_readings ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


def get_history(hours=24):
    """
    返回过去 N 小时数据，按 5 分钟窗口聚合均值。
    返回: [{"time": "HH:MM", "soil_moisture": 42.0, "temperature": 22.5,
            "humidity": 65.0, "light": 30000}, ...]
    """
    now = int(time.time())
    start_ts = now - hours * 3600

    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                (timestamp / 300) * 300 AS window_start,
                AVG(soil_moisture) AS soil_moisture,
                AVG(temperature) AS temperature,
                AVG(humidity) AS humidity,
                AVG(light) AS light
            FROM sensor_readings
            WHERE timestamp >= ?
            GROUP BY window_start
            ORDER BY window_start ASC
            """,
            (start_ts,)
        ).fetchall()

    result = []
    for row in rows:
        window_start = row["window_start"]
        if window_start is None:
            continue
        t = time.strftime("%H:%M", time.localtime(window_start))
        result.append({
            "time": t,
            "soil_moisture": round(row["soil_moisture"], 2) if row["soil_moisture"] is not None else None,
            "temperature": round(row["temperature"], 1) if row["temperature"] is not None else None,
            "humidity": round(row["humidity"], 1) if row["humidity"] is not None else None,
            "light": round(row["light"]) if row["light"] is not None else None,
        })
    return result


def insert_irrigation_log(action, reason, created_at=None):
    """插入一条灌溉操作日志（created_at 可选，用于补录/演示数据）。"""
    with _get_conn() as conn:
        if created_at:
            conn.execute(
                "INSERT INTO irrigation_logs (action, reason, created_at) VALUES (?, ?, ?)",
                (action, reason, created_at),
            )
        else:
            conn.execute(
                "INSERT INTO irrigation_logs (action, reason) VALUES (?, ?)",
                (action, reason),
            )
        conn.commit()


def clear_demo_irrigation_logs():
    """删除一键演示生成的灌溉日志（reason 以「模拟演示」开头），返回条数。"""
    with _get_conn() as conn:
        cur = conn.execute("DELETE FROM irrigation_logs WHERE reason LIKE '模拟演示%'")
        conn.commit()
    return cur.rowcount


def get_recent_logs(limit=20):
    """返回最近 N 条灌溉日志 list[dict]。"""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT action, reason, created_at FROM irrigation_logs ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# 设备管理
# ---------------------------------------------------------------------------
def get_devices(group_id=None):
    """返回设备列表（含所属分组名），可按分组过滤。"""
    sql = ("SELECT d.*, g.name AS group_name FROM devices d "
           "LEFT JOIN device_groups g ON d.group_id = g.id")
    params = []
    if group_id is not None:
        sql += " WHERE d.group_id = ?"
        params.append(group_id)
    sql += " ORDER BY d.id ASC"
    with _get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def get_device(device_id):
    """按 device_id 返回设备 dict（含分组名），无则 None。"""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT d.*, g.name AS group_name FROM devices d "
            "LEFT JOIN device_groups g ON d.group_id = g.id "
            "WHERE d.device_id = ?", (device_id,)
        ).fetchone()
    return dict(row) if row else None


def upsert_device(device_id, name, location, status="offline", last_seen=None):
    """插入或更新设备。"""
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO devices (device_id, name, location, status, last_seen)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(device_id) DO UPDATE SET
               name=excluded.name, location=excluded.location,
               status=excluded.status, last_seen=excluded.last_seen""",
            (device_id, name, location, status, last_seen)
        )
        conn.commit()


def delete_device(device_id):
    """删除设备。"""
    with _get_conn() as conn:
        conn.execute("DELETE FROM devices WHERE device_id = ?", (device_id,))
        conn.commit()


# ---------------------------------------------------------------------------
# 设备分组
# ---------------------------------------------------------------------------
def insert_group(name, location="", description="", leader=None):
    """新增分组，返回 (ok, id_or_err)。"""
    try:
        with _get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO device_groups (name, location, description, leader) "
                "VALUES (?, ?, ?, ?)", (name, location, description, leader)
            )
            conn.commit()
            return True, cur.lastrowid
    except sqlite3.IntegrityError:
        return False, "分组名称已存在"


def get_groups():
    """分组列表，附带设备数与在线数。"""
    with _get_conn() as conn:
        rows = conn.execute(
            """SELECT g.*,
                      COUNT(d.id) AS device_count,
                      SUM(CASE WHEN d.status = 'online' THEN 1 ELSE 0 END) AS online_count
               FROM device_groups g
               LEFT JOIN devices d ON d.group_id = g.id
               GROUP BY g.id
               ORDER BY g.id ASC"""
        ).fetchall()
    return [dict(r) for r in rows]


def get_group(group_id):
    """按 id 取分组。"""
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM device_groups WHERE id = ?", (group_id,)).fetchone()
    return dict(row) if row else None


def update_group(group_id, name, location, description, leader):
    """更新分组，返回 (ok, group_or_err)。"""
    if not get_group(group_id):
        return False, "分组不存在"
    try:
        with _get_conn() as conn:
            conn.execute(
                "UPDATE device_groups SET name = ?, location = ?, description = ?, leader = ? "
                "WHERE id = ?", (name, location, description, leader, group_id)
            )
            conn.commit()
    except sqlite3.IntegrityError:
        return False, "分组名称已存在"
    return True, get_group(group_id)


def delete_group(group_id):
    """删除分组：组内设备自动转为未分组。"""
    if not get_group(group_id):
        return False
    with _get_conn() as conn:
        conn.execute("UPDATE devices SET group_id = NULL WHERE group_id = ?", (group_id,))
        conn.execute("DELETE FROM device_groups WHERE id = ?", (group_id,))
        conn.commit()
    return True


def assign_device_group(device_id, group_id):
    """把设备分配到分组（group_id=None 表示移出分组）。"""
    with _get_conn() as conn:
        cur = conn.execute(
            "UPDATE devices SET group_id = ? WHERE device_id = ?", (group_id, device_id)
        )
        conn.commit()
    return cur.rowcount > 0


def get_group_stats():
    """分组总览：分组数、设备总数、在线设备、未分组设备。"""
    with _get_conn() as conn:
        groups = conn.execute("SELECT COUNT(*) AS c FROM device_groups").fetchone()["c"]
        total = conn.execute("SELECT COUNT(*) AS c FROM devices").fetchone()["c"]
        online = conn.execute(
            "SELECT COUNT(*) AS c FROM devices WHERE status = 'online'"
        ).fetchone()["c"]
        ungrouped = conn.execute(
            "SELECT COUNT(*) AS c FROM devices WHERE group_id IS NULL"
        ).fetchone()["c"]
    return {"groups": groups, "devices": total, "online": online, "ungrouped": ungrouped}


# ---------------------------------------------------------------------------
# 告警
# ---------------------------------------------------------------------------
def get_alerts(status=None, limit=100):
    """返回告警列表，可按状态过滤。"""
    with _get_conn() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM alerts WHERE status = ? ORDER BY id DESC LIMIT ?",
                (status, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
    return [dict(row) for row in rows]


def get_alert(alert_id):
    """按 id 取单条告警，无则 None。"""
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
    return dict(row) if row else None


def insert_alert(type_, level, message, device_id):
    """插入一条告警。"""
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO alerts (type, level, message, device_id) VALUES (?, ?, ?, ?)",
            (type_, level, message, device_id)
        )
        conn.commit()


def handle_alert(alert_id):
    """将告警标记为已处理。"""
    with _get_conn() as conn:
        conn.execute(
            "UPDATE alerts SET status='handled', handled_at=CURRENT_TIMESTAMP WHERE id=?",
            (alert_id,)
        )
        conn.commit()


def get_alert_rules():
    """返回所有告警规则。"""
    with _get_conn() as conn:
        rows = conn.execute("SELECT * FROM alert_rules ORDER BY id ASC").fetchall()
    return [dict(row) for row in rows]


def upsert_alert_rule(metric, condition, threshold, level, enabled=1, rule_id=None):
    """插入或更新告警规则。"""
    with _get_conn() as conn:
        if rule_id:
            conn.execute(
                "UPDATE alert_rules SET metric=?, condition=?, threshold=?, level=?, enabled=? WHERE id=?",
                (metric, condition, threshold, level, enabled, rule_id)
            )
        else:
            conn.execute(
                "INSERT INTO alert_rules (metric, condition, threshold, level, enabled) VALUES (?, ?, ?, ?, ?)",
                (metric, condition, threshold, level, enabled)
            )
        conn.commit()


def delete_alert_rule(rule_id):
    """删除告警规则。"""
    with _get_conn() as conn:
        conn.execute("DELETE FROM alert_rules WHERE id=?", (rule_id,))
        conn.commit()


def record_rule_trigger(rule_id, metric=None, level=None, device_id=None):
    """规则命中计数 +1、更新最近触发时间，并写入命中明细。"""
    with _get_conn() as conn:
        conn.execute(
            "UPDATE alert_rules SET trigger_count = COALESCE(trigger_count, 0) + 1, "
            "last_triggered_at = CURRENT_TIMESTAMP WHERE id = ?", (rule_id,)
        )
        conn.execute(
            "INSERT INTO rule_hits (rule_id, metric, level, device_id) VALUES (?, ?, ?, ?)",
            (rule_id, metric, level or "warning", device_id),
        )
        conn.commit()


def get_rule_trend(days=7):
    """最近 N 天规则命中趋势：按天 × 规则聚合，返回 labels / series / total。"""
    days = max(1, min(30, int(days)))
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT date(created_at) AS d, rule_id, metric, level, COUNT(*) AS c "
            "FROM rule_hits WHERE date(created_at) >= date('now', ?) "
            "GROUP BY d, rule_id, metric, level",
            ("-%d days" % (days - 1),),
        ).fetchall()
    today = datetime.date.today()
    labels = [(today - datetime.timedelta(days=days - 1 - i)).isoformat()
              for i in range(days)]
    grouped = {}
    for r in rows:
        key = (r["rule_id"], r["metric"] or "unknown", r["level"] or "warning")
        g = grouped.setdefault(key, {"rule_id": r["rule_id"], "metric": r["metric"],
                                     "level": r["level"], "counts": {}})
        g["counts"][r["d"]] = r["c"]
    series = [{
        "rule_id": g["rule_id"],
        "metric": g["metric"],
        "level": g["level"],
        "data": [g["counts"].get(d, 0) for d in labels],
    } for g in grouped.values()]
    series.sort(key=lambda s: sum(s["data"]), reverse=True)
    return {"labels": labels, "series": series,
            "total": sum(sum(s["data"]) for s in series)}


def get_rule_top(days=7, limit=5):
    """最近 N 天规则命中 Top 排行：按规则聚合命中次数并补全规则配置。"""
    days = max(1, min(30, int(days)))
    limit = max(1, min(10, int(limit)))
    window = "-%d days" % (days - 1)
    with _get_conn() as conn:
        total = conn.execute(
            "SELECT COUNT(*) AS c FROM rule_hits WHERE date(created_at) >= date('now', ?)",
            (window,),
        ).fetchone()["c"]
        rows = conn.execute(
            "SELECT rule_id, COALESCE(metric, 'unknown') AS metric, "
            "COALESCE(level, 'warning') AS level, COUNT(*) AS hits, "
            "MAX(created_at) AS last_hit_at "
            "FROM rule_hits WHERE date(created_at) >= date('now', ?) "
            "GROUP BY rule_id ORDER BY hits DESC, last_hit_at DESC LIMIT ?",
            (window, limit),
        ).fetchall()
        rules = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM alert_rules").fetchall()}
    items = []
    for i, r in enumerate(rows, 1):
        rule = rules.get(r["rule_id"]) or {}
        items.append({
            "rank": i,
            "rule_id": r["rule_id"],
            "metric": r["metric"],
            "level": r["level"],
            "condition": rule.get("condition"),
            "threshold": rule.get("threshold"),
            "enabled": rule.get("enabled"),
            "hits": r["hits"],
            "share": round(r["hits"] * 100.0 / total, 1) if total else 0,
            "last_hit_at": r["last_hit_at"],
        })
    return {"days": days, "limit": limit, "total": total, "items": items}


def set_rules_enabled(enabled, rule_ids=None):
    """批量启用/停用规则（rule_ids 为空表示全部），返回受影响条数。"""
    sql = "UPDATE alert_rules SET enabled = ?"
    params = [1 if enabled else 0]
    if rule_ids:
        sql += " WHERE id IN (%s)" % ",".join("?" * len(rule_ids))
        params += list(rule_ids)
    with _get_conn() as conn:
        cur = conn.execute(sql, params)
        conn.commit()
    return cur.rowcount


def get_rule_stats():
    """规则统计：总数、启用数、累计命中次数。"""
    with _get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM alert_rules").fetchone()["c"]
        enabled = conn.execute(
            "SELECT COUNT(*) AS c FROM alert_rules WHERE enabled = 1"
        ).fetchone()["c"]
        triggers = conn.execute(
            "SELECT COALESCE(SUM(trigger_count), 0) AS c FROM alert_rules"
        ).fetchone()["c"]
    return {"total": total, "enabled": enabled,
            "disabled": total - enabled, "triggers": triggers}


# ---------------------------------------------------------------------------
# 灌溉调度
# ---------------------------------------------------------------------------
def get_schedules():
    """返回所有灌溉调度。"""
    with _get_conn() as conn:
        rows = conn.execute("SELECT * FROM irrigation_schedules ORDER BY id ASC").fetchall()
    return [dict(row) for row in rows]


def insert_schedule(name, start_time, duration, enabled=1):
    """插入灌溉调度。"""
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO irrigation_schedules (name, start_time, duration, enabled) VALUES (?, ?, ?, ?)",
            (name, start_time, duration, enabled)
        )
        conn.commit()


def update_schedule(schedule_id, name, start_time, duration, enabled):
    """更新灌溉调度。"""
    with _get_conn() as conn:
        conn.execute(
            "UPDATE irrigation_schedules SET name=?, start_time=?, duration=?, enabled=? WHERE id=?",
            (name, start_time, duration, enabled, schedule_id)
        )
        conn.commit()


def delete_schedule(schedule_id):
    """删除灌溉调度。"""
    with _get_conn() as conn:
        conn.execute("DELETE FROM irrigation_schedules WHERE id=?", (schedule_id,))
        conn.commit()


# ---------------------------------------------------------------------------
# 统计概览
# ---------------------------------------------------------------------------
def get_overview_stats(hours=24):
    """返回系统概览统计：读数总数、设备数、告警数、灌溉次数。"""
    now = int(time.time())
    start_ts = now - hours * 3600
    with _get_conn() as conn:
        reading_count = conn.execute(
            "SELECT COUNT(*) AS c FROM sensor_readings WHERE timestamp >= ?", (start_ts,)
        ).fetchone()["c"]
        device_count = conn.execute("SELECT COUNT(*) AS c FROM devices").fetchone()["c"]
        alert_count = conn.execute(
            "SELECT COUNT(*) AS c FROM alerts WHERE status='pending'"
        ).fetchone()["c"]
        irrigation_count = conn.execute(
            "SELECT COUNT(*) AS c FROM irrigation_logs WHERE action='start'"
        ).fetchone()["c"]
    return {
        "reading_count": reading_count,
        "device_count": device_count,
        "alert_count": alert_count,
        "irrigation_count": irrigation_count,
    }


# ---------------------------------------------------------------------------
# 执行器
# ---------------------------------------------------------------------------
def get_actuators():
    """返回所有执行器 list[dict]。"""
    with _get_conn() as conn:
        rows = conn.execute("SELECT * FROM actuators ORDER BY id ASC").fetchall()
    return [dict(row) for row in rows]


def get_actuator(name):
    """按 name 返回执行器 dict，无则 None。"""
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM actuators WHERE name = ?", (name,)).fetchone()
    return dict(row) if row else None


def update_actuator(name, status):
    """更新执行器状态(on/off)。"""
    with _get_conn() as conn:
        conn.execute(
            "UPDATE actuators SET status=?, last_changed=CURRENT_TIMESTAMP WHERE name=?",
            (status, name)
        )
        conn.commit()


def upsert_actuator(name, label, status="off", device_id=None):
    """插入或更新执行器。"""
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO actuators (name, label, status, device_id)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(name) DO UPDATE SET
               label=excluded.label, status=excluded.status, device_id=excluded.device_id""",
            (name, label, status, device_id)
        )
        conn.commit()


# ---------------------------------------------------------------------------
# 农事日志
# ---------------------------------------------------------------------------
def get_farm_logs(limit=100):
    """返回最近 N 条农事日志。"""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM farm_logs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


def insert_farm_log(type_, description, operator="系统"):
    """插入一条农事日志。"""
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO farm_logs (type, description, operator) VALUES (?, ?, ?)",
            (type_, description, operator)
        )
        conn.commit()


def delete_farm_log(log_id):
    """删除农事日志。"""
    with _get_conn() as conn:
        conn.execute("DELETE FROM farm_logs WHERE id=?", (log_id,))
        conn.commit()


# ---------------------------------------------------------------------------
# 溯源批次
# ---------------------------------------------------------------------------
def get_batches():
    """返回所有溯源批次。"""
    with _get_conn() as conn:
        rows = conn.execute("SELECT * FROM traceability_batches ORDER BY id DESC").fetchall()
    return [dict(row) for row in rows]


def get_batch(batch_no):
    """按批次号返回批次 dict。"""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM traceability_batches WHERE batch_no = ?", (batch_no,)
        ).fetchone()
    return dict(row) if row else None


def insert_batch(batch_no, crop_name, sowing_date, harvest_date=None,
                 quality_status="pending", notes=""):
    """插入溯源批次。"""
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO traceability_batches
               (batch_no, crop_name, sowing_date, harvest_date, quality_status, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (batch_no, crop_name, sowing_date, harvest_date, quality_status, notes)
        )
        conn.commit()


def update_batch_quality(batch_no, quality_status):
    """更新批次质检状态。"""
    with _get_conn() as conn:
        conn.execute(
            "UPDATE traceability_batches SET quality_status=? WHERE batch_no=?",
            (quality_status, batch_no)
        )
        conn.commit()


# ---------------------------------------------------------------------------
# 农业知识库
# ---------------------------------------------------------------------------
def get_knowledge(category=None, limit=100):
    """返回知识库文章列表，可按分类过滤。"""
    with _get_conn() as conn:
        if category:
            rows = conn.execute(
                "SELECT id, category, title, summary, author, views, created_at "
                "FROM knowledge_articles WHERE category=? ORDER BY id DESC LIMIT ?",
                (category, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, category, title, summary, author, views, created_at "
                "FROM knowledge_articles ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
    return [dict(row) for row in rows]


def get_knowledge_article(article_id):
    """按 ID 返回知识库文章全文，并累加阅读量。"""
    with _get_conn() as conn:
        conn.execute(
            "UPDATE knowledge_articles SET views=views+1 WHERE id=?", (article_id,)
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM knowledge_articles WHERE id=?", (article_id,)
        ).fetchone()
    return dict(row) if row else None


def insert_knowledge(category, title, summary, content, author="农技专家"):
    """插入知识库文章。"""
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO knowledge_articles (category, title, summary, content, author) "
            "VALUES (?, ?, ?, ?, ?)",
            (category, title, summary, content, author)
        )
        conn.commit()


def update_knowledge(article_id, category=None, title=None, summary=None,
                     content=None, author=None):
    """更新知识库文章（只更新传入的字段）。"""
    fields = []
    vals = []
    if category is not None: fields.append("category=?"); vals.append(category)
    if title is not None: fields.append("title=?"); vals.append(title)
    if summary is not None: fields.append("summary=?"); vals.append(summary)
    if content is not None: fields.append("content=?"); vals.append(content)
    if author is not None: fields.append("author=?"); vals.append(author)
    if not fields: return None
    vals.append(article_id)
    with _get_conn() as conn:
        conn.execute(
            "UPDATE knowledge_articles SET " + ", ".join(fields) + " WHERE id=?", vals
        )
        conn.commit()
        row = conn.execute("SELECT * FROM knowledge_articles WHERE id=?",
                           (article_id,)).fetchone()
    return dict(row) if row else None


def delete_knowledge(article_id):
    """删除知识库文章。"""
    with _get_conn() as conn:
        conn.execute("DELETE FROM knowledge_articles WHERE id=?", (article_id,))
        conn.commit()


# ---------------------------------------------------------------------------
# 农业新闻
# ---------------------------------------------------------------------------
def get_news(category=None, limit=50):
    """返回新闻列表，置顶优先，可按分类过滤。"""
    with _get_conn() as conn:
        if category:
            rows = conn.execute(
                "SELECT id, category, title, summary, source, is_top, views, created_at "
                "FROM news_articles WHERE category=? "
                "ORDER BY is_top DESC, id DESC LIMIT ?",
                (category, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, category, title, summary, source, is_top, views, created_at "
                "FROM news_articles ORDER BY is_top DESC, id DESC LIMIT ?", (limit,)
            ).fetchall()
    return [dict(row) for row in rows]


def get_news_article(news_id):
    """按 ID 返回新闻全文，并累加阅读量。"""
    with _get_conn() as conn:
        conn.execute(
            "UPDATE news_articles SET views=views+1 WHERE id=?", (news_id,)
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM news_articles WHERE id=?", (news_id,)
        ).fetchone()
    return dict(row) if row else None


def insert_news(category, title, summary, content, source="AgriSense 资讯", is_top=0):
    """插入新闻。"""
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO news_articles (category, title, summary, content, source, is_top) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (category, title, summary, content, source, is_top)
        )
        conn.commit()


def update_news(news_id, category=None, title=None, summary=None,
                 content=None, source=None, is_top=None):
    """更新新闻（只更新传入的字段）。"""
    fields = []
    vals = []
    if category is not None: fields.append("category=?"); vals.append(category)
    if title is not None: fields.append("title=?"); vals.append(title)
    if summary is not None: fields.append("summary=?"); vals.append(summary)
    if content is not None: fields.append("content=?"); vals.append(content)
    if source is not None: fields.append("source=?"); vals.append(source)
    if is_top is not None: fields.append("is_top=?"); vals.append(is_top)
    if not fields: return None
    vals.append(news_id)
    with _get_conn() as conn:
        conn.execute(
            "UPDATE news_articles SET " + ", ".join(fields) + " WHERE id=?", vals
        )
        conn.commit()
        row = conn.execute("SELECT * FROM news_articles WHERE id=?",
                           (news_id,)).fetchone()
    return dict(row) if row else None


def delete_news(news_id):
    """删除新闻。"""
    with _get_conn() as conn:
        conn.execute("DELETE FROM news_articles WHERE id=?", (news_id,))
        conn.commit()


def toggle_news_top(news_id, is_top):
    """切换新闻置顶。"""
    with _get_conn() as conn:
        conn.execute("UPDATE news_articles SET is_top=? WHERE id=?",
                     (1 if is_top else 0, news_id))
        conn.commit()


# ---------------------------------------------------------------------------
# 客服留言
# ---------------------------------------------------------------------------
def insert_feedback(name, contact, type_, message):
    """插入一条客服留言。"""
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO feedback (name, contact, type, message) VALUES (?, ?, ?, ?)",
            (name, contact, type_, message)
        )
        conn.commit()


def get_feedback_list(limit=100, status=None):
    """返回客服留言列表，可按状态过滤。"""
    with _get_conn() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM feedback WHERE status=? ORDER BY id DESC LIMIT ?",
                (status, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM feedback ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
    return [dict(row) for row in rows]


def mark_feedback(feedback_id, status, reply=None):
    """处理客服留言（pending→resolved 等）。"""
    with _get_conn() as conn:
        if reply is not None:
            conn.execute(
                "UPDATE feedback SET status=?, reply=? WHERE id=?",
                (status, reply, feedback_id)
            )
        else:
            conn.execute(
                "UPDATE feedback SET status=? WHERE id=?", (status, feedback_id)
            )
        conn.commit()


def delete_feedback(feedback_id):
    """删除客服留言。"""
    with _get_conn() as conn:
        conn.execute("DELETE FROM feedback WHERE id=?", (feedback_id,))
        conn.commit()


# ---------------------------------------------------------------------------
# 站点内容管理（FAQ / 关于我们 / 隐私政策 / 服务条款等）
# ---------------------------------------------------------------------------
def get_site_content(key):
    """按 key 返回站点内容，不存在返回 None。"""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM site_contents WHERE key=?", (key,)
        ).fetchone()
    return dict(row) if row else None


def list_site_contents():
    """返回所有站点内容条目。"""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM site_contents ORDER BY key ASC"
        ).fetchall()
    return [dict(row) for row in rows]


def upsert_site_content(key, title, content):
    """插入或更新站点内容。"""
    with _get_conn() as conn:
        existing = conn.execute(
            "SELECT key FROM site_contents WHERE key=?", (key,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE site_contents SET title=?, content=?, updated_at=CURRENT_TIMESTAMP "
                "WHERE key=?",
                (title, content, key)
            )
        else:
            conn.execute(
                "INSERT INTO site_contents (key, title, content) VALUES (?, ?, ?)",
                (key, title, content)
            )
        conn.commit()


def delete_site_content(key):
    """删除站点内容。"""
    with _get_conn() as conn:
        conn.execute("DELETE FROM site_contents WHERE key=?", (key,))
        conn.commit()


# ---------------------------------------------------------------------------
# 用户与会话
# ---------------------------------------------------------------------------
def _row_to_user(row):
    """把 users 行转成 dict（不含密码哈希与盐）。"""
    if row is None:
        return None
    return {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"],
        "role": row["role"],
        "status": row["status"],
        "last_login": row["last_login"],
        "created_at": row["created_at"],
    }


def get_users():
    """用户列表。"""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM users ORDER BY id ASC"
        ).fetchall()
    return [_row_to_user(r) for r in rows]


def get_user_by_username(username):
    """按用户名查用户（含密码哈希，仅供登录校验使用）。"""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
    if row is None:
        return None
    user = _row_to_user(row)
    user["password_hash"] = row["password_hash"]
    user["salt"] = row["salt"]
    return user


def get_user(user_id):
    """按 ID 查用户。"""
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _row_to_user(row)


def create_user(username, password_hash, salt, display_name=None,
                role="viewer", status="active"):
    """新增用户，返回新用户 ID。"""
    with _get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, salt, display_name, role, status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (username, password_hash, salt, display_name or username, role, status)
        )
        conn.commit()
        return cur.lastrowid


def update_user(user_id, role=None, status=None, display_name=None,
                password_hash=None, salt=None):
    """更新用户信息（只更新传入的字段）。"""
    fields = []
    values = []
    if role is not None:
        fields.append("role = ?")
        values.append(role)
    if status is not None:
        fields.append("status = ?")
        values.append(status)
    if display_name is not None:
        fields.append("display_name = ?")
        values.append(display_name)
    if password_hash is not None:
        fields.append("password_hash = ?")
        values.append(password_hash)
    if salt is not None:
        fields.append("salt = ?")
        values.append(salt)
    if not fields:
        return False
    values.append(user_id)
    with _get_conn() as conn:
        conn.execute("UPDATE users SET " + ", ".join(fields) + " WHERE id = ?", values)
        conn.commit()
        return True


def delete_user(user_id):
    """删除用户。"""
    with _get_conn() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()


def touch_user_login(username):
    """记录最近登录时间。"""
    with _get_conn() as conn:
        conn.execute(
            "UPDATE users SET last_login = datetime('now', 'localtime') WHERE username = ?",
            (username,)
        )
        conn.commit()


def create_session(token, username, role, expires_at):
    """创建登录会话。"""
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO sessions (token, username, role, expires_at) VALUES (?, ?, ?, ?)",
            (token, username, role, expires_at)
        )
        conn.commit()


def get_session(token):
    """取会话，过期返回 None。"""
    if not token:
        return None
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE token = ?", (token,)
        ).fetchone()
    if row is None:
        return None
    if row["expires_at"] < int(time.time()):
        delete_session(token)
        return None
    return {"token": row["token"], "username": row["username"], "role": row["role"]}


def delete_session(token):
    """删除会话（退出登录）。"""
    with _get_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()


def clean_expired_sessions():
    """清理过期会话。"""
    with _get_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (int(time.time()),))
        conn.commit()


# ---------------------------------------------------------------------------
# 个人中心：登录日志 / 修改密码 / 会话管理
# ---------------------------------------------------------------------------
def insert_login_log(username, ip, user_agent, success):
    """记录一次登录尝试（success 传 0/1）。"""
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO login_logs (username, ip, user_agent, success) VALUES (?, ?, ?, ?)",
            (username, ip, user_agent, 1 if success else 0)
        )
        conn.commit()


def get_login_logs(username, limit=20):
    """返回指定用户最近 N 条登录日志 list[dict]。"""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT id, username, ip, user_agent, success, created_at "
            "FROM login_logs WHERE username = ? ORDER BY id DESC LIMIT ?",
            (username, limit)
        ).fetchall()
    return [dict(row) for row in rows]


def update_user_password(username, password_hash, salt):
    """用户本人修改密码。"""
    with _get_conn() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, salt = ? WHERE username = ?",
            (password_hash, salt, username)
        )
        conn.commit()


def delete_other_sessions(username, keep_token):
    """删除该用户除 keep_token 外的所有会话（退出其他设备）。"""
    with _get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM sessions WHERE username = ? AND token != ?",
            (username, keep_token)
        )
        conn.commit()
        return cur.rowcount


# ---------------------------------------------------------------------------
# 操作审计
# ---------------------------------------------------------------------------
def insert_audit_log(username, action, target=None, detail=None, ip=None):
    """记录一次操作审计。"""
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO audit_logs (username, action, target, detail, ip) VALUES (?, ?, ?, ?, ?)",
            (username, action, target, detail, ip)
        )
        conn.commit()


def get_audit_logs(limit=100, username=None, action=None, keyword=None):
    """查询审计日志，支持按用户名/动作/关键词过滤，按 id 倒序。"""
    sql = "SELECT * FROM audit_logs WHERE 1=1"
    params = []
    if username:
        sql += " AND username = ?"
        params.append(username)
    if action:
        sql += " AND action = ?"
        params.append(action)
    if keyword:
        sql += " AND (target LIKE ? OR detail LIKE ?)"
        params.extend(["%" + keyword + "%", "%" + keyword + "%"])
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with _get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def get_audit_stats():
    """审计统计：总数、今日数、涉及用户数、动作分类数。"""
    with _get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM audit_logs").fetchone()["c"]
        today = conn.execute(
            "SELECT COUNT(*) AS c FROM audit_logs WHERE date(created_at) = date('now', 'localtime')"
        ).fetchone()["c"]
        users = conn.execute(
            "SELECT COUNT(DISTINCT username) AS c FROM audit_logs"
        ).fetchone()["c"]
        actions = conn.execute(
            "SELECT COUNT(DISTINCT action) AS c FROM audit_logs"
        ).fetchone()["c"]
    return {"total": total, "today": today, "users": users, "actions": actions}


# ---------------------------------------------------------------------------
# 统计报表聚合函数
# ---------------------------------------------------------------------------

def _day_bounds(days=7):
    """返回 [start_ts, end_ts, daily_start_ts_list]。"""
    now = int(time.time())
    # 以天为粒度，对齐到当日 00:00
    today_zero = now - (now % 86400)
    end_ts = now
    start_ts = today_zero - (days - 1) * 86400
    # 每天的起始时间戳，便于前端 x 轴渲染
    daily_ts = [start_ts + i * 86400 for i in range(days)]
    return start_ts, end_ts, daily_ts


def _day_label(ts):
    """时间戳 -> 'MM-DD'。"""
    lt = time.localtime(ts)
    return "%02d-%02d" % (lt.tm_mon, lt.tm_mday)


def get_environment_daily(days=7):
    """按天返回环境指标均值序列。"""
    start_ts, end_ts, daily_ts = _day_bounds(days)
    with _get_conn() as conn:
        rows = conn.execute("""
            SELECT (timestamp / 86400) * 86400 AS day_ts,
                   AVG(soil_moisture) AS avg_moisture,
                   MIN(soil_moisture) AS min_moisture,
                   MAX(soil_moisture) AS max_moisture,
                   AVG(temperature)    AS avg_temp,
                   MIN(temperature)    AS min_temp,
                   MAX(temperature)    AS max_temp,
                   AVG(humidity)       AS avg_hum,
                   AVG(light)          AS avg_light
            FROM sensor_readings
            WHERE timestamp >= ? AND timestamp <= ?
            GROUP BY day_ts
            ORDER BY day_ts ASC
        """, (start_ts, end_ts)).fetchall()

    bucket = {r["day_ts"]: r for r in rows}
    labels = []
    moisture, temp, hum, light = [], [], [], []
    min_moisture, max_moisture = [], []
    for dts in daily_ts:
        labels.append(_day_label(dts))
        r = bucket.get(dts)
        if r is None:
            moisture.append(None); temp.append(None); hum.append(None); light.append(None)
            min_moisture.append(None); max_moisture.append(None)
        else:
            # round 到 1 位小数；None 保护（有些字段可能全 NULL）
            def _round(v):
                return round(v, 1) if v is not None else None
            moisture.append(_round(r["avg_moisture"]))
            min_moisture.append(_round(r["min_moisture"]))
            max_moisture.append(_round(r["max_moisture"]))
            temp.append(_round(r["avg_temp"]))
            hum.append(_round(r["avg_hum"]))
            light.append(int(r["avg_light"]) if r["avg_light"] is not None else None)
    return {
        "labels": labels,
        "daily_ts": daily_ts,
        "avg_moisture": moisture,
        "min_moisture": min_moisture,
        "max_moisture": max_moisture,
        "avg_temp": temp,
        "avg_humidity": hum,
        "avg_light": light,
    }


def get_irrigation_stats(days=7):
    """灌溉统计：按天 start 次数 + 所有 start/stop 列表。"""
    start_ts, end_ts, daily_ts = _day_bounds(days)
    with _get_conn() as conn:
        # 按天统计 start 次数
        rows = conn.execute("""
            SELECT (strftime('%s', created_at) / 86400) * 86400 AS day_ts,
                   COUNT(*) AS cnt
            FROM irrigation_logs
            WHERE action='start'
            GROUP BY day_ts
            ORDER BY day_ts ASC
        """).fetchall()
        all_logs = conn.execute("""
            SELECT action, reason, created_at
            FROM irrigation_logs
            ORDER BY id DESC
            LIMIT 500
        """).fetchall()
        # 期间内的 start 次数
        total_start = conn.execute("""
            SELECT COUNT(*) AS c FROM irrigation_logs WHERE action='start'
        """).fetchone()["c"]
        total_stop = conn.execute("""
            SELECT COUNT(*) AS c FROM irrigation_logs WHERE action='stop'
        """).fetchone()["c"]

    bucket = {r["day_ts"]: r["cnt"] for r in rows}
    labels = [_day_label(dts) for dts in daily_ts]
    counts = [bucket.get(dts, 0) for dts in daily_ts]

    recent = []
    # irrigation_logs.created_at 是 TEXT (CURRENT_TIMESTAMP)，用 strptime 解析
    for log in all_logs:
        recent.append({
            "action": log["action"],
            "reason": log["reason"],
            "created_at": log["created_at"],
        })

    return {
        "labels": labels,
        "daily_start": counts,
        "total_start": total_start,
        "total_stop": total_stop,
        "recent": recent[:30],
    }


def get_alert_stats(days=7):
    """告警统计：等级分布 + 类型分布 + 按天数量。"""
    start_ts, end_ts, daily_ts = _day_bounds(days)
    with _get_conn() as conn:
        level_rows = conn.execute("""
            SELECT level, COUNT(*) AS c FROM alerts GROUP BY level
        """).fetchall()
        type_rows = conn.execute("""
            SELECT type, COUNT(*) AS c FROM alerts GROUP BY type ORDER BY c DESC LIMIT 10
        """).fetchall()
        trend_rows = conn.execute("""
            SELECT (strftime('%s', created_at) / 86400) * 86400 AS day_ts,
                   COUNT(*) AS c
            FROM alerts
            GROUP BY day_ts
            ORDER BY day_ts ASC
        """).fetchall()

    level_map = {"critical": "严重", "warning": "警告", "info": "提示"}
    level_dist = [
        {"name": level_map.get(r["level"], r["level"]), "value": r["c"], "raw": r["level"]}
        for r in level_rows
    ]
    type_dist = [{"name": r["type"], "value": r["c"]} for r in type_rows]

    bucket = {r["day_ts"]: r["c"] for r in trend_rows}
    labels = [_day_label(dts) for dts in daily_ts]
    trend = [bucket.get(dts, 0) for dts in daily_ts]

    return {
        "level_distribution": level_dist,
        "type_distribution": type_dist,
        "labels": labels,
        "trend": trend,
        "total": sum([d["value"] for d in level_dist]),
    }


def get_farm_activity_stats():
    """农事活动类型分布。"""
    with _get_conn() as conn:
        rows = conn.execute("""
            SELECT type, COUNT(*) AS c FROM farm_logs GROUP BY type ORDER BY c DESC
        """).fetchall()
    return [{"name": r["type"], "value": r["c"]} for r in rows]


def get_batch_stats():
    """溯源批次质量状态分布 + 作物类型分布。"""
    with _get_conn() as conn:
        status_rows = conn.execute("""
            SELECT quality_status, COUNT(*) AS c FROM traceability_batches GROUP BY quality_status
        """).fetchall()
        crop_rows = conn.execute("""
            SELECT crop_name, COUNT(*) AS c FROM traceability_batches GROUP BY crop_name ORDER BY c DESC
        """).fetchall()
    status_map = {
        "qualified": "已合格",
        "unqualified": "不合格",
        "pending": "待质检",
        "harvested": "已采收",
    }
    status_dist = [
        {"name": status_map.get(r["quality_status"], r["quality_status"]),
         "value": r["c"], "raw": r["quality_status"]}
        for r in status_rows
    ]
    crop_dist = [{"name": r["crop_name"], "value": r["c"]} for r in crop_rows]
    return {"status_distribution": status_dist, "crop_distribution": crop_dist}


# ---------------------------------------------------------------------------
# 数据导出（CSV）
# ---------------------------------------------------------------------------
# 可导出的数据表白名单：data_type -> (表名, 时间过滤列)
EXPORT_TABLES = {
    "sensor_readings": ("sensor_readings", "created_at"),
    "irrigation_logs": ("irrigation_logs", "created_at"),
    "alerts": ("alerts", "created_at"),
    "farm_logs": ("farm_logs", "created_at"),
    "traceability_batches": ("traceability_batches", "created_at"),
    "audit_logs": ("audit_logs", "created_at"),
}


def export_rows(data_type, start_date=None, end_date=None, limit=10000):
    """
    按数据类型导出记录（用于 CSV）。
    - start_date/end_date: 'YYYY-MM-DD'，按 created_at 过滤（含当天）
    - 返回 (columns, rows)，rows 为 list[tuple]
    """
    if data_type not in EXPORT_TABLES:
        return None, None
    table, time_col = EXPORT_TABLES[data_type]

    sql = "SELECT * FROM %s WHERE 1=1" % table
    params = []
    if start_date:
        sql += " AND date(%s) >= date(?)" % time_col
        params.append(start_date)
    if end_date:
        sql += " AND date(%s) <= date(?)" % time_col
        params.append(end_date)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(min(limit, 50000))

    with _get_conn() as conn:
        cur = conn.execute(sql, params)
        columns = [d[0] for d in cur.description]
        rows = cur.fetchall()
    return columns, [tuple(row) for row in rows]


def export_count(data_type):
    """各数据类型的可导出总条数（供导出中心展示）。"""
    if data_type not in EXPORT_TABLES:
        return 0
    table, _ = EXPORT_TABLES[data_type]
    with _get_conn() as conn:
        return conn.execute("SELECT COUNT(*) AS c FROM %s" % table).fetchone()["c"]


# ---------------------------------------------------------------------------
# 系统设置（key-value 持久化）
# ---------------------------------------------------------------------------

def get_setting(key, default=None):
    """读取单个设置项，不存在返回 default。"""
    with _get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    """写入/更新设置项。"""
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP",
            (key, str(value))
        )
        conn.commit()


def get_all_settings():
    """返回全部设置 dict {key: value}。"""
    with _get_conn() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    return {r["key"]: r["value"] for r in rows}


# ---------------------------------------------------------------------------
# 站内通知
# ---------------------------------------------------------------------------

def insert_notification(username, title, content, ntype="info"):
    """给单个用户投递一条通知。"""
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO notifications (username, title, content, type) VALUES (?, ?, ?, ?)",
            (username, title, content, ntype)
        )
        conn.commit()


def notify_roles(roles, title, content, ntype="info"):
    """给指定角色的全部启用用户投递通知（如告警广播给 admin/operator）。"""
    with _get_conn() as conn:
        users = conn.execute(
            "SELECT username FROM users WHERE status = 'active' AND role IN (%s)"
            % ",".join("?" * len(roles)),
            roles
        ).fetchall()
        for u in users:
            conn.execute(
                "INSERT INTO notifications (username, title, content, type) VALUES (?, ?, ?, ?)",
                (u["username"], title, content, ntype)
            )
        conn.commit()
    return len(users)


def get_notifications(username, limit=20, unread_only=False):
    """某用户的通知列表（id 倒序）+ 未读数。"""
    sql = "SELECT * FROM notifications WHERE username = ?"
    params = [username]
    if unread_only:
        sql += " AND is_read = 0"
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(min(limit, 200))
    with _get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
        unread = conn.execute(
            "SELECT COUNT(*) AS c FROM notifications WHERE username = ? AND is_read = 0",
            (username,)
        ).fetchone()["c"]
    return [dict(r) for r in rows], unread


def mark_notification_read(nid, username):
    """标记本人一条通知为已读。"""
    with _get_conn() as conn:
        cur = conn.execute(
            "UPDATE notifications SET is_read = 1 WHERE id = ? AND username = ?",
            (nid, username)
        )
        conn.commit()
    return cur.rowcount > 0


def mark_all_notifications_read(username):
    """本人通知全部已读，返回更新条数。"""
    with _get_conn() as conn:
        cur = conn.execute(
            "UPDATE notifications SET is_read = 1 WHERE username = ? AND is_read = 0",
            (username,)
        )
        conn.commit()
    return cur.rowcount


# ---------------------------------------------------------------------------
# 工单系统
# ---------------------------------------------------------------------------
def _next_ticket_no(conn):
    """生成工单号 TK-XXXX（按最大 id 递增）。"""
    row = conn.execute("SELECT MAX(id) AS m FROM tickets").fetchone()
    return "TK-%04d" % ((row["m"] or 0) + 1)


def insert_ticket(title, description, creator, ttype="ops", priority="medium",
                  alert_id=None, assignee=None):
    """创建工单，返回新工单 dict。"""
    with _get_conn() as conn:
        ticket_no = _next_ticket_no(conn)
        cur = conn.execute(
            "INSERT INTO tickets (ticket_no, title, description, type, priority, "
            "status, alert_id, creator, assignee, updated_at) "
            "VALUES (?, ?, ?, ?, ?, 'open', ?, ?, ?, CURRENT_TIMESTAMP)",
            (ticket_no, title, description, ttype, priority, alert_id, creator, assignee)
        )
        conn.commit()
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


def get_tickets(status=None, assignee=None, creator=None, keyword=None, limit=200):
    """工单列表（id 倒序），支持状态/指派人/创建人/关键词过滤。"""
    sql = "SELECT * FROM tickets WHERE 1=1"
    params = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if assignee:
        sql += " AND assignee = ?"
        params.append(assignee)
    if creator:
        sql += " AND creator = ?"
        params.append(creator)
    if keyword:
        sql += " AND (title LIKE ? OR description LIKE ? OR ticket_no LIKE ?)"
        like = "%" + keyword + "%"
        params += [like, like, like]
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(min(limit, 500))
    with _get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def get_ticket(ticket_id):
    """按 id 取单个工单，无则 None。"""
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    return dict(row) if row else None


def update_ticket(ticket_id, fields):
    """更新工单字段（白名单），返回更新后的工单 dict 或 None。"""
    allowed = ("title", "description", "type", "priority", "status",
               "assignee", "resolution")
    sets, params = [], []
    for key in allowed:
        if key in fields:
            sets.append(key + " = ?")
            params.append(fields[key])
    if not sets:
        return get_ticket(ticket_id)
    sets.append("updated_at = CURRENT_TIMESTAMP")
    # 状态进入已解决/已关闭时记录关闭时间
    if fields.get("status") in ("resolved", "closed"):
        sets.append("closed_at = CURRENT_TIMESTAMP")
    sql = "UPDATE tickets SET " + ", ".join(sets) + " WHERE id = ?"
    params.append(ticket_id)
    with _get_conn() as conn:
        conn.execute(sql, params)
        conn.commit()
    return get_ticket(ticket_id)


def delete_ticket(ticket_id):
    """删除工单，返回是否删除成功。"""
    with _get_conn() as conn:
        cur = conn.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
        conn.commit()
    return cur.rowcount > 0


def get_ticket_stats():
    """工单统计：按状态与优先级汇总。"""
    with _get_conn() as conn:
        by_status = {r["status"]: r["c"] for r in conn.execute(
            "SELECT status, COUNT(*) AS c FROM tickets GROUP BY status"
        ).fetchall()}
        by_priority = {r["priority"]: r["c"] for r in conn.execute(
            "SELECT priority, COUNT(*) AS c FROM tickets GROUP BY priority"
        ).fetchall()}
        open_unassigned = conn.execute(
            "SELECT COUNT(*) AS c FROM tickets WHERE status = 'open' "
            "AND (assignee IS NULL OR assignee = '')"
        ).fetchone()["c"]
        total = conn.execute("SELECT COUNT(*) AS c FROM tickets").fetchone()["c"]
    return {
        "total": total,
        "by_status": by_status,
        "by_priority": by_priority,
        "open_unassigned": open_unassigned,
    }


# ---------------------------------------------------------------------------
# 数据维护：时序表统计、过期清理、VACUUM、维护日志
# ---------------------------------------------------------------------------
# 允许清理的时序表（均含 created_at 文本时间列）
CLEANABLE_TABLES = {
    "sensor_readings": "传感器读数",
    "alerts": "告警记录",
    "notifications": "站内通知",
    "login_logs": "登录日志",
    "irrigation_logs": "灌溉日志",
}


def get_db_size():
    """返回数据库文件大小（字节）。"""
    db_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.getsize(os.path.join(db_dir, DATABASE_PATH))


def get_table_stats():
    """各可维护表的行数与时间范围。"""
    stats = []
    with _get_conn() as conn:
        for table, label in CLEANABLE_TABLES.items():
            row = conn.execute(
                "SELECT COUNT(*) AS c, MIN(created_at) AS earliest, "
                "MAX(created_at) AS latest FROM " + table
            ).fetchone()
            stats.append({
                "table": table,
                "label": label,
                "rows": row["c"],
                "earliest": row["earliest"],
                "latest": row["latest"],
            })
    return stats


def count_expired_rows(table, days):
    """统计指定表中早于 days 天的行数（预览用）。"""
    if table not in CLEANABLE_TABLES:
        return 0
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM " + table +
            " WHERE created_at < datetime('now', 'localtime', ?)",
            ("-%d days" % int(days),)
        ).fetchone()
    return row["c"]


def cleanup_old_rows(table, days):
    """删除指定表中早于 days 天的数据，返回删除行数。"""
    if table not in CLEANABLE_TABLES:
        return 0
    with _get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM " + table +
            " WHERE created_at < datetime('now', 'localtime', ?)",
            ("-%d days" % int(days),)
        )
        conn.commit()
    return cur.rowcount


def vacuum_db():
    """VACUUM 压缩数据库文件，返回压缩前后大小 (before, after)。"""
    before = get_db_size()
    with _get_conn() as conn:
        conn.execute("VACUUM")
    return before, get_db_size()


def insert_maintenance_log(action, target_table, removed_rows, retention_days,
                           mode, operator, detail=None):
    """写入一条维护日志。"""
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO maintenance_logs (action, target_table, removed_rows, "
            "retention_days, mode, operator, detail) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (action, target_table, removed_rows, retention_days, mode, operator, detail)
        )
        conn.commit()


def get_maintenance_logs(limit=50):
    """维护日志列表（id 倒序）。"""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM maintenance_logs ORDER BY id DESC LIMIT ?",
            (min(limit, 200),)
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# 固件版本管理（OTA）
# ---------------------------------------------------------------------------
def insert_firmware(version, device_model, filename, stored_name, size,
                    checksum, changelog, uploaded_by):
    """登记一个固件版本，返回 (ok, err_or_id)。"""
    try:
        with _get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO firmware_versions (version, device_model, filename, "
                "stored_name, size, checksum, changelog, uploaded_by) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (version, device_model, filename, stored_name, size,
                 checksum, changelog, uploaded_by)
            )
            conn.commit()
            return True, cur.lastrowid
    except sqlite3.IntegrityError:
        return False, "该型号下版本号已存在"


def get_firmware_list(device_model=None):
    """固件列表（按型号过滤，id 倒序）。"""
    with _get_conn() as conn:
        if device_model:
            rows = conn.execute(
                "SELECT * FROM firmware_versions WHERE device_model = ? ORDER BY id DESC",
                (device_model,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM firmware_versions ORDER BY id DESC"
            ).fetchall()
    return [dict(r) for r in rows]


def get_firmware(fw_id):
    """按 id 取固件记录。"""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM firmware_versions WHERE id = ?", (fw_id,)
        ).fetchone()
    return dict(row) if row else None


def get_latest_firmware(device_model):
    """取某型号标记为最新的固件，无则取 id 最大的一条。"""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM firmware_versions WHERE device_model = ? AND is_latest = 1 "
            "ORDER BY id DESC LIMIT 1", (device_model,)
        ).fetchone()
        if row is None:
            row = conn.execute(
                "SELECT * FROM firmware_versions WHERE device_model = ? "
                "ORDER BY id DESC LIMIT 1", (device_model,)
            ).fetchone()
    return dict(row) if row else None


def set_firmware_latest(fw_id):
    """将指定固件设为该型号最新版（同型号其他记录取消标记）。"""
    fw = get_firmware(fw_id)
    if not fw:
        return None
    with _get_conn() as conn:
        conn.execute(
            "UPDATE firmware_versions SET is_latest = 0 WHERE device_model = ?",
            (fw["device_model"],)
        )
        conn.execute("UPDATE firmware_versions SET is_latest = 1 WHERE id = ?", (fw_id,))
        conn.commit()
    return get_firmware(fw_id)


def inc_firmware_download(fw_id):
    """下载计数 +1。"""
    with _get_conn() as conn:
        conn.execute(
            "UPDATE firmware_versions SET downloads = downloads + 1 WHERE id = ?",
            (fw_id,)
        )
        conn.commit()


def delete_firmware(fw_id):
    """删除固件记录，返回被删记录（供调用方删文件）。"""
    fw = get_firmware(fw_id)
    if not fw:
        return None
    with _get_conn() as conn:
        conn.execute("DELETE FROM firmware_versions WHERE id = ?", (fw_id,))
        conn.commit()
    return fw
