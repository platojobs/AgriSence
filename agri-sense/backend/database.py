# -*- coding: utf-8 -*-
"""
AgriSense 数据库操作层
- 使用 sqlite3，每次操作都通过 with sqlite3.connect(...) as conn
- conn.row_factory = sqlite3.Row，便于按字段名取值
"""

import os
import sqlite3
import time

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
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
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
        conn.commit()


def insert_reading(device_id, soil_moisture, raw, timestamp,
                   temperature=None, humidity=None, light=None):
    """插入一条传感器读数（温湿度光照可选）。"""
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO sensor_readings (device_id, soil_moisture, temperature, humidity, light, raw, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (device_id, soil_moisture, temperature, humidity, light, raw, timestamp)
        )
        conn.commit()


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


def insert_irrigation_log(action, reason):
    """插入一条灌溉操作日志。"""
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO irrigation_logs (action, reason) VALUES (?, ?)",
            (action, reason)
        )
        conn.commit()


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
def get_devices():
    """返回所有设备 list[dict]。"""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM devices ORDER BY id ASC"
        ).fetchall()
    return [dict(row) for row in rows]


def get_device(device_id):
    """按 device_id 返回设备 dict，无则 None。"""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM devices WHERE device_id = ?", (device_id,)
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
