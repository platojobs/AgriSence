# -*- coding: utf-8 -*-
"""
AgriSense 灌溉决策逻辑
纯函数，便于单元测试，不依赖 Flask / 数据库上下文。
"""


def decide(soil_moisture, threshold_low=30, threshold_high=70,
           rain_prob=0, rain_mm=0.0):
    """
    根据土壤墒情、上下限阈值与未来降水决策灌溉动作。

    :param soil_moisture: 土壤墒情百分比（0-100），可为 None
    :param threshold_low:  灌溉下限（低于此值开始灌溉）
    :param threshold_high: 灌溉上限（高于此值停止灌溉）
    :param rain_prob:      未来 24 小时最大降雨概率（%）
    :param rain_mm:        未来 24 小时预计降水量（mm）
    :return: (action, reason)
        action: "start" | "stop" | "hold"
    """
    if soil_moisture is None:
        return "hold", "暂无数据"
    if soil_moisture < threshold_low:
        # 天气联动：即将降雨时推迟灌溉，避免水资源浪费与根系缺氧
        if rain_prob >= 70 and rain_mm >= 3:
            return "hold", "墒情偏低但未来 24 小时降雨概率 %d%%、预计降水 %.1fmm，建议推迟灌溉" % (rain_prob, rain_mm)
        if rain_prob >= 60:
            return "hold", "墒情偏低但未来 24 小时降雨概率 %d%%，建议延后灌溉并持续观察" % rain_prob
        return "start", "土壤墒情低于下限"
    elif soil_moisture > threshold_high:
        return "stop", "土壤墒情高于上限"
    return "hold", "墒情正常"
