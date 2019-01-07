# -*- coding: utf-8 -*-
"""
AgriSense 气象服务

当前实现为「季节模型 + 确定性伪随机」的本地气象源：
  - 以城市与日期为随机种子，同一城市同一天生成的数据稳定可复现
  - 温度遵循年周期（季节）与日周期（昼夜）正弦模型
  - 降水概率随季节变化，并驱动天气现象、农事指数与灌溉建议

生产环境替换方式：把 get_weather() 内部换成和风天气 / OpenWeatherMap /
open-meteo 的真实 HTTP 请求，保持返回结构不变即可，上层代码无需改动。
"""

import math
import random
import time
from datetime import date, datetime, timedelta

# 预设城市：纬度与气候参数不同，便于演示不同气候带的数据差异
CITIES = {
    "杭州": {"lat": 30.29, "lon": 120.16, "annual": 17.0, "amp": 12.5, "humidity": 74},
    "北京": {"lat": 39.90, "lon": 116.41, "annual": 12.5, "amp": 15.5, "humidity": 56},
    "广州": {"lat": 23.13, "lon": 113.26, "annual": 22.5, "amp": 8.0, "humidity": 80},
    "成都": {"lat": 30.57, "lon": 104.07, "annual": 16.5, "amp": 9.5, "humidity": 82},
    "西安": {"lat": 34.34, "lon": 108.94, "annual": 14.0, "amp": 13.5, "humidity": 62},
    "哈尔滨": {"lat": 45.80, "lon": 126.53, "annual": 4.5, "amp": 20.0, "humidity": 60},
}

# 天气现象码（参考 WMO code 的简化子集）
WEATHER_CODES = {
    0: ("晴", "bi-sun", "#f6b93b"),
    1: ("多云转晴", "bi-cloud-sun", "#f0a830"),
    2: ("多云", "bi-cloud", "#8fa3b0"),
    3: ("阴", "bi-clouds", "#8fa3b0"),
    45: ("雾", "bi-cloud-haze2", "#9aa8b2"),
    51: ("毛毛雨", "bi-cloud-drizzle", "#5aa9dd"),
    61: ("小雨", "bi-cloud-rain", "#4a9edb"),
    63: ("中雨", "bi-cloud-rain-heavy", "#3d85c6"),
    65: ("大雨", "bi-cloud-rain-heavy", "#2f6fa8"),
    71: ("小雪", "bi-cloud-snow", "#9fb8d4"),
    80: ("阵雨", "bi-cloud-rain", "#4a9edb"),
    95: ("雷阵雨", "bi-cloud-lightning-rain", "#c0392b"),
}

WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

# 天气缓存：避免仪表盘/规则引擎每次调用都重算
_cache = {}
CACHE_TTL = 600  # 秒


def _city_seed(city):
    """稳定字符串种子（不使用内置 hash，避免进程间随机化）。"""
    return sum((i + 1) * ord(ch) for i, ch in enumerate(city)) % 100000


def _season_temp(cfg, day):
    """年周期温度模型：1 月中旬最低，7 月中旬最高。"""
    doy = day.timetuple().tm_yday
    return cfg["annual"] + cfg["amp"] * math.sin(2 * math.pi * (doy - 105) / 365.0)


def _rain_season(cfg, month):
    """降水概率的季节基线：夏季多雨，秋冬干燥。"""
    if month in (6, 7, 8):
        return 45.0
    if month in (4, 5, 9):
        return 36.0
    if month in (3, 10):
        return 28.0
    return 18.0 + (cfg["humidity"] - 60) * 0.4


def _code_by_rain(rain_prob, temp_max):
    """根据降水概率与气温推断天气现象码。"""
    if rain_prob >= 85:
        return 95 if temp_max >= 25 else 65
    if rain_prob >= 72:
        return 65 if temp_max >= 20 else 63
    if rain_prob >= 58:
        return 63 if temp_max >= 15 else 71
    if rain_prob >= 45:
        return 61
    if rain_prob >= 32:
        return 3
    if rain_prob >= 18:
        return 2
    return 1 if rain_prob >= 8 else 0


def _daily_weather(city, day):
    """生成某城市某天的日级天气。"""
    cfg = CITIES[city]
    seed = _city_seed(city) * 100000 + day.year * 10000 + day.month * 100 + day.day
    rng = random.Random(seed)

    mean = _season_temp(cfg, day) + rng.uniform(-1.8, 1.8)
    spread = rng.uniform(4.2, 7.0)
    t_max = mean + spread
    t_min = mean - spread

    rain_base = _rain_season(cfg, day.month)
    rain_prob = max(0.0, min(95.0, rain_base + rng.uniform(-18, 28)))
    rain_mm = 0.0
    if rain_prob >= 50:
        rain_mm = round(rng.uniform(0.6, 8.0) + (rain_prob - 50) * 0.22, 1)

    code = _code_by_rain(rain_prob, t_max)
    name, icon, color = WEATHER_CODES[code]
    wind = round(rng.uniform(1.2, 6.4), 1)

    return {
        "date": day.strftime("%Y-%m-%d"),
        "weekday": WEEKDAY_CN[day.weekday()],
        "code": code,
        "text": name,
        "icon": icon,
        "color": color,
        "temp_max": round(t_max, 1),
        "temp_min": round(t_min, 1),
        "rain_prob": int(round(rain_prob)),
        "rain_mm": rain_mm,
        "wind": wind,
    }


def _temp_at(daily, hour):
    """按日周期曲线插值某时刻气温：5 点最低、17 点最高。"""
    t_min, t_max = daily["temp_min"], daily["temp_max"]
    ratio = 0.5 - 0.5 * math.cos(2 * math.pi * (hour - 5) / 24.0)
    return round(t_min + (t_max - t_min) * ratio, 1)


def _hourly_forecast(city, now):
    """未来 24 小时逐时天气。"""
    hours = []
    for i in range(24):
        point = now + timedelta(hours=i)
        day = point.date()
        daily = _daily_weather(city, day)
        temp = _temp_at(daily, point.hour)
        # 逐时降水概率围绕日均值波动，午后对流更强
        rng = random.Random(_city_seed(city) + int(point.timestamp()) // 3600)
        bump = 8 if 14 <= point.hour <= 19 else 0
        prob = max(0, min(99, daily["rain_prob"] + bump + rng.randint(-10, 10)))
        hours.append({
            "time": point.strftime("%H:00"),
            "datetime": point.strftime("%m-%d %H:%M"),
            "temp": temp,
            "rain_prob": prob,
        })
    return hours


def _farming_index(current, today):
    """农事适宜度评分与建议。"""
    score = 100
    tips = []

    if current["temp"] >= 35:
        score -= 30
        tips.append("高温时段避免中午作业，注意人畜防暑与作物蒸腾补水")
    elif current["temp"] <= 2:
        score -= 30
        tips.append("低温易发生霜冻，建议覆盖地膜或启用保温设施")
    elif 16 <= current["temp"] <= 28:
        tips.append("温度适宜，适合开展施肥、整枝等田间作业")
    else:
        score -= 8

    if today["rain_prob"] >= 80:
        score -= 30
        tips.append("降雨概率很高，暂停喷药与施肥，防止药液流失")
    elif today["rain_prob"] >= 55:
        score -= 15
        tips.append("有降雨可能，喷药请安排在雨前 4 小时以外或改期")
    elif today["rain_prob"] <= 20 and current["humidity"] <= 55:
        score -= 8
        tips.append("空气干燥，注意灌溉与通风，降低病害发生风险")

    if current["wind"] >= 5.5:
        score -= 12
        tips.append("风力较大，无人机植保与喷灌作业需谨慎")

    score = max(10, min(100, score))
    if score >= 80:
        level, level_text = "good", "适宜"
    elif score >= 55:
        level, level_text = "normal", "较适宜"
    else:
        level, level_text = "bad", "不适宜"

    if not tips:
        tips.append("气象条件平稳，可按计划开展日常田间管理")

    return {"score": score, "level": level, "text": level_text, "tips": tips}


def _weather_alerts(daily_list, current):
    """根据预报生成气象预警。"""
    alerts = []
    for d in daily_list[:3]:
        if d["temp_max"] >= 35:
            alerts.append({
                "type": "高温预警",
                "level": "warning",
                "message": "%s %s 最高气温 %.1f℃，注意作物日灼与灌溉补水" % (d["date"], d["weekday"], d["temp_max"]),
            })
        if d["temp_min"] <= 0:
            alerts.append({
                "type": "霜冻预警",
                "level": "danger",
                "message": "%s 最低气温 %.1f℃，建议提前采取防冻措施" % (d["date"], d["temp_min"]),
            })
        if d["rain_prob"] >= 80 and d["rain_mm"] >= 15:
            alerts.append({
                "type": "暴雨预警",
                "level": "danger",
                "message": "%s 降雨概率 %d%%，预计降水 %.1fmm，请检查排水沟渠" % (d["date"], d["rain_prob"], d["rain_mm"]),
            })
    if current["wind"] >= 10.5:
        alerts.append({"type": "大风预警", "level": "warning", "message": "当前风力 %.1f 级，请加固棚膜" % current["wind"]})

    # 同类型预警只保留最近一条，避免刷屏
    seen = set()
    unique = []
    for a in alerts:
        if a["type"] in seen:
            continue
        seen.add(a["type"])
        unique.append(a)
    return unique


def get_weather(city="杭州"):
    """
    获取指定城市的气象数据（当前 + 24 小时 + 7 天预报 + 农事指数 + 预警）。

    :param city: 城市名，需在 CITIES 中
    :return: dict
    """
    if city not in CITIES:
        city = "杭州"

    cached = _cache.get(city)
    now_ts = time.time()
    if cached and now_ts - cached["ts"] < CACHE_TTL:
        return cached["data"]

    now = datetime.now()
    today = _daily_weather(city, now.date())
    daily_list = [_daily_weather(city, now.date() + timedelta(days=i)) for i in range(7)]
    hourly = _hourly_forecast(city, now)

    cur_temp = _temp_at(today, now.hour)
    cfg = CITIES[city]
    # 湿度与气温负相关，正午最低
    humidity = cfg["humidity"] + (today["temp_min"] + today["temp_max"]) / 2.0 - cur_temp
    humidity = max(30, min(98, int(round(humidity + random.Random(int(now_ts) // 600).uniform(-4, 4)))))
    feels_like = round(cur_temp + (humidity - 60) * 0.06 - today["wind"] * 0.25, 1)

    current = {
        "temp": cur_temp,
        "feels_like": feels_like,
        "humidity": humidity,
        "text": today["text"],
        "code": today["code"],
        "icon": today["icon"],
        "color": today["color"],
        "wind": today["wind"],
        "rain_prob": today["rain_prob"],
        "rain_mm": today["rain_mm"],
        "pressure": 1013 - int(cfg["annual"] * 0.15 + (cur_temp - cfg["annual"]) * 0.35),
        "visibility": round(20 - today["rain_prob"] * 0.12, 1),
        "uv": max(0, int(round(9 - today["rain_prob"] * 0.08))),
        "update_time": now.strftime("%Y-%m-%d %H:%M:%S"),
    }

    data = {
        "city": city,
        "cities": list(CITIES.keys()),
        "lat": cfg["lat"],
        "lon": cfg["lon"],
        "current": current,
        "today": today,
        "hourly": hourly,
        "daily": daily_list,
        "farming_index": _farming_index(current, today),
        "alerts": _weather_alerts(daily_list, current),
        "source": "本地季节模型（可替换为真实气象 API）",
    }

    _cache[city] = {"ts": now_ts, "data": data}
    return data


def rain_summary(city="杭州"):
    """
    未来 24 小时降水摘要，供灌溉决策使用。

    :return: {"rain_prob": 最大降水概率, "rain_mm": 累计降水量}
    """
    weather = get_weather(city)
    next_24 = weather["hourly"][:24]
    max_prob = max(h["rain_prob"] for h in next_24)
    rain_mm = weather["today"]["rain_mm"] + weather["daily"][1]["rain_mm"] * 0.5
    # 日均降水为 0 但逐时概率较高时，按概率估算一个量级，保证"概率-降水量"口径一致
    if rain_mm == 0 and max_prob >= 55:
        rain_mm = round((max_prob - 40) * 0.18, 1)
    return {"rain_prob": int(max_prob), "rain_mm": round(rain_mm, 1)}
