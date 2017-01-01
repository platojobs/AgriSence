# -*- coding: utf-8 -*-
"""
AgriSense 灌溉决策逻辑
纯函数，便于单元测试，不依赖 Flask / 数据库上下文。
"""


def decide(soil_moisture, threshold_low=30, threshold_high=70):
    """
    根据土壤墒情与上下限阈值决策灌溉动作。

    :param soil_moisture: 土壤墒情百分比（0-100），可为 None
    :param threshold_low:  灌溉下限（低于此值开始灌溉）
    :param threshold_high: 灌溉上限（高于此值停止灌溉）
    :return: (action, reason)
        action: "start" | "stop" | "hold"
    """
    if soil_moisture is None:
        return "hold", "暂无数据"
    if soil_moisture < threshold_low:
        return "start", "土壤墒情低于下限"
    elif soil_moisture > threshold_high:
        return "stop", "土壤墒情高于上限"
    return "hold", "墒情正常"
