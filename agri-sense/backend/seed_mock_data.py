# -*- coding: utf-8 -*-
"""
生成模拟数据并写入 SQLite，便于前端页面联调展示。

模拟指标：
- 土壤墒情：缓慢下降 + 波动，低于阈值触发灌溉后回升
- 温度：日内正弦曲线（白天高、夜间低），范围 12~32°C
- 湿度：与温度负相关的日内曲线，范围 40~90%
- 光照：白天有值、夜间为 0 的半正弦曲线，范围 0~120000 lux

用法：
    cd backend
    python seed_mock_data.py
"""

import math
import random
import time

from database import (
    init_db, insert_reading, insert_irrigation_log, get_history,
    upsert_device, insert_alert, upsert_alert_rule, insert_schedule,
    upsert_actuator, insert_farm_log, insert_batch,
    insert_knowledge, insert_news, upsert_site_content,
    get_user_by_username, create_user,
)


def seed():
    init_db()

    now = int(time.time())
    device_id = "esp32_001"

    total_points = 288      # 过去 24 小时
    interval = 300          # 5 分钟

    readings = []
    for i in range(total_points):
        ts = now - (total_points - i) * interval
        hour_frac = (ts % 86400) / 3600.0  # 当天的小时数（0~24）

        # ---- 土壤墒情：整体缓慢下降 + 正弦波动 ----
        base = 70 - (i / total_points) * 50
        wave = math.sin(i / 12.0) * 8
        noise = random.uniform(-3, 3)
        moisture = max(5, min(95, base + wave + noise))
        raw = int(max(800, min(3200, 3000 - moisture * 18 + random.uniform(-20, 20))))

        # ---- 温度：日内正弦，凌晨最低、午后最高 ----
        # 用 hour_frac 拟合：最低约在 5 点，最高约在 14 点
        temp_phase = (hour_frac - 5) / 24.0 * 2 * math.pi
        temperature = 22 + 10 * math.sin(temp_phase) + random.uniform(-0.8, 0.8)
        temperature = round(max(8, min(38, temperature)), 1)

        # ---- 湿度：与温度负相关 ----
        humidity = 75 - (temperature - 15) * 1.6 + random.uniform(-3, 3)
        humidity = round(max(25, min(98, humidity)), 1)

        # ---- 光照：白天半正弦，夜间为 0 ----
        # 日出 6 点、日落 19 点
        if 6 <= hour_frac <= 19:
            day_phase = (hour_frac - 6) / 13.0 * math.pi
            light = int(120000 * math.sin(day_phase) + random.uniform(-2000, 2000))
            light = max(0, light)
        else:
            light = 0

        readings.append((ts, round(moisture, 1), raw, temperature, humidity, light))

    for ts, moisture, raw, temp, hum, light in readings:
        insert_reading(device_id, moisture, raw, ts,
                       temperature=temp, humidity=hum, light=light)

    # 灌溉日志：墒情跌破 30 记录 start，回升到 55 以上记录 stop
    irrigated = False
    for ts, moisture, raw, temp, hum, light in readings:
        if not irrigated and moisture < 30:
            insert_irrigation_log("start", "土壤墒情低于下限")
            irrigated = True
        elif irrigated and moisture > 55:
            insert_irrigation_log("stop", "土壤墒情高于上限")
            irrigated = False

    print(f"已写入 {total_points} 条传感器读数")
    print(f"历史聚合点数：{len(get_history(hours=24))}")

    # ---- 设备 ----
    upsert_device("esp32_001", "温室A区-土壤监测站", "1号温室东侧", "online", now)
    upsert_device("esp32_002", "温室B区-土壤监测站", "2号温室西侧", "online", now)
    upsert_device("esp32_003", "田间气象站", "大田中央", "online", now)
    upsert_device("esp32_004", "蓄水池水位监测", "蓄水池旁", "offline", now - 3600)

    # ---- 告警规则 ----
    upsert_alert_rule("soil_moisture", "<", 30, "critical", 1)
    upsert_alert_rule("soil_moisture", ">", 80, "warning", 1)
    upsert_alert_rule("temperature", ">", 35, "warning", 1)
    upsert_alert_rule("temperature", "<", 5, "critical", 1)
    upsert_alert_rule("humidity", "<", 30, "info", 1)

    # ---- 告警记录 ----
    insert_alert("soil_moisture", "critical", "土壤墒情低于下限（12.7%）", "esp32_001")
    insert_alert("temperature", "warning", "温室温度偏高（32.5°C）", "esp32_001")
    insert_alert("device_offline", "warning", "设备 esp32_004 离线超过 1 小时", "esp32_004")

    # ---- 灌溉调度 ----
    insert_schedule("清晨灌溉", "06:00", 30, 1)
    insert_schedule("午间补水", "12:30", 15, 1)
    insert_schedule("夜间灌溉", "20:00", 45, 0)

    # ---- 执行器 ----
    upsert_actuator("irrigation_valve", "灌溉阀门", "off", "esp32_001")
    upsert_actuator("fertilizer_pump", "施肥泵", "off", "esp32_001")
    upsert_actuator("fan", "通风风机", "off", "esp32_002")
    upsert_actuator("shade_net", "遮阳网", "off", "esp32_002")

    # ---- 农事日志 ----
    insert_farm_log("施肥", "追施复合肥 20kg/亩，采用水肥一体化", "张师傅")
    insert_farm_log("打药", "喷施生物农药防治蚜虫", "李师傅")
    insert_farm_log("除草", "人工除草，清理棚间杂草", "王师傅")
    insert_farm_log("采收", "采收成熟番茄约 150kg", "张师傅")

    # ---- 溯源批次 ----
    insert_batch("AGRI-20260520-001", "番茄", "2026-05-20", "2026-08-15", "qualified", "温室A区种植，全程智慧农业监测")
    insert_batch("AGRI-20260610-002", "黄瓜", "2026-06-10", "2026-09-01", "pending", "温室B区种植")

    # ---- 农业知识库 ----
    knowledge = [
        ("种植技术", "番茄设施栽培全周期管理要点",
         "从育苗、定植到采收的完整管理流程，涵盖温度、光照、整枝、留果等关键环节。",
         "一、育苗期\n选用抗病品种，基质育苗保持日温25-28°C、夜温15-18°C。出苗后适当控水蹲苗，防止徒长。\n\n二、定植期\n幼苗4-5片真叶时定植，株距40cm、行距60cm。定植后浇透定根水，缓苗期保持土壤湿润。\n\n三、开花坐果期\n白天温度控制在22-28°C，夜间12-15°C。采用熊蜂授粉或震荡授粉提高坐果率。每穗留果3-4个，及时疏花疏果。\n\n四、膨果采收期\n增施钾肥，保持土壤墒情在60-75%。单干整枝，及时摘除老叶病叶，改善通风透光条件。"),
        ("种植技术", "黄瓜嫁接育苗技术规范",
         "以南瓜为砧木的黄瓜靠接/插接育苗方法，显著提高抗病性与产量。",
         "嫁接是防治黄瓜枯萎病、提高耐低温能力的核心技术。\n\n一、砧木选择\n常用黑籽南瓜或白籽南瓜作砧木，根系发达、抗土传病害。\n\n二、播种安排\n黄瓜比砧木早播2-3天（插接法）或砧木早播3-4天（靠接法）。\n\n三、嫁接操作\n插接法：砧木子叶展平时，去除生长点，用竹签斜插成孔，将黄瓜接穗削成楔形插入。\n\n四、嫁接后管理\n前3天遮光保湿，温度25-28°C、湿度95%以上；逐步通风见光，7-10天后进入正常管理。"),
        ("种植技术", "设施草莓高架基质栽培技术",
         "摆脱土壤连作障碍的现代化草莓种植模式，配合水肥一体化实现精准管理。",
         "高架基质栽培是设施草莓转型升级的主要方向。\n\n一、栽培槽与基质\n采用H型或A型栽培架，槽内填充椰糠:珍珠岩=3:1的混合基质。\n\n二、定植\n9月上中旬定植，株距18-20cm，弓背朝外、深不埋心、浅不露根。\n\n三、环境管理\n现蕾期白天25-28°C、夜间8-10°C；结果期白天20-25°C、夜间5-8°C。配合补光灯调节光周期。\n\n四、水肥管理\nEC值控制在0.8-1.2mS/cm，少量多次滴灌，避免基质过湿诱发灰霉病。"),
        ("病虫害防治", "番茄早疫病与晚疫病的识别与防治",
         "两种常见番茄病害的症状差异、发病条件及综合防治方案。",
         "一、早疫病识别\n叶片出现同心轮纹状褐色病斑，边缘有黄色晕圈，多在结果期发生。高温高湿、植株衰弱时易发病。\n\n二、晚疫病识别\n叶缘出现水渍状病斑，叶背有白色霉层，蔓延极快，低温高湿（15-22°C、湿度>85%）时暴发。\n\n三、农业防治\n合理密植、及时整枝打杈、膜下滴灌降低棚内湿度；与非茄科作物轮作3年以上。\n\n四、化学防治\n早疫病：发病初期喷施百菌清或代森锰锌；晚疫病：喷施烯酰吗啉、霜霉威盐酸盐，5-7天一次，连续2-3次。"),
        ("病虫害防治", "蚜虫绿色防控技术指南",
         "以生物防治和物理防治为主的蚜虫综合治理方案，减少化学农药使用。",
         "蚜虫是设施蔬菜最重要的刺吸式害虫之一，传播病毒病危害极大。\n\n一、物理防治\n棚室通风口覆盖40-60目防虫网；棚内悬挂黄色粘虫板（每亩20-30块，高出植株10-15cm）。\n\n二、生物防治\n释放异色瓢虫、蚜茧蜂等天敌，益害比1:100时控害效果最佳；喷施苦参碱、印楝素等植物源农药。\n\n三、生态调控\n行间种植芹菜、韭菜等驱避植物；避免偏施氮肥造成植株嫩绿招虫。\n\n四、应急用药\n虫口密度大时选用吡虫啉、啶虫脒，注意轮换用药防止抗性。"),
        ("病虫害防治", "灰霉病高发的环境诱因与防控",
         "低温高湿季节灰霉病的发病规律，重点讲解湿度管理与药剂选择。",
         "灰霉病是冬春设施栽培的第一大病害，危害番茄、黄瓜、草莓等多种作物。\n\n一、发病条件\n温度18-23°C、相对湿度>90%、光照不足时最易暴发。病菌从残花、伤口侵入。\n\n二、湿度管理是关键\n采用膜下滴灌或滴灌；上午升温通风排湿；避免阴雨天浇水。\n\n三、农事操作\n及时摘除病花病果，蘸花药剂中添加腐霉利；蘸花后及时摘除残留花瓣。\n\n四、药剂防治\n发病初期喷施腐霉利、异菌脲或啶酰菌胺，重点喷花和幼果。阴雨天可用烟剂熏棚。"),
        ("水肥管理", "水肥一体化系统的设计与日常运维",
         "滴灌施肥系统的组成、肥料选择、灌溉制度制定及常见故障排查。",
         "水肥一体化可实现节水30-50%、节肥20-30%，是设施农业的核心装备。\n\n一、系统组成\n水源→首部枢纽（水泵、过滤器、施肥机）→输配水管网→滴灌带。过滤器建议120目叠片式。\n\n二、肥料选择\n必须选用全水溶性肥料，常用尿素、硝酸钾、磷酸二氢钾及专用水溶肥。避免使用含杂质肥料堵塞滴头。\n\n三、灌溉制度\n苗期少量多次，结果期每次每亩灌水8-12方，EC值控制在1.0-2.0mS/cm。\n\n四、日常运维\n每周冲洗管网；每月检测滴头流量均匀度；施肥结束后继续灌清水15分钟冲洗管道。"),
        ("水肥管理", "土壤墒情监测与精准灌溉决策",
         "如何根据土壤含水量数据制定灌溉阈值，实现按需供水。",
         "精准灌溉的核心是『测土定水』。\n\n一、墒情指标\n土壤相对含水量60-75%为多数蔬菜适宜区间；低于45%需立即灌溉，高于85%应控水防病。\n\n二、监测布点\n传感器埋深20-30cm（主要根系层），每个灌溉分区至少1个监测点。\n\n三、灌溉决策\n结合作物生育期需水规律：苗期控水蹲苗、开花期适度控水、结果期保持墒情稳定。\n\n四、数据应用\n将墒情曲线与灌溉记录对照分析，可优化灌溉周期，避免凭经验浇水造成的忽干忽湿。"),
        ("智慧农业", "农业物联网在设施大棚中的应用架构",
         "感知层-传输层-平台层-应用层的四层架构解析，以及ESP32节点的部署实践。",
         "农业物联网是智慧农业的基础设施。\n\n一、感知层\n部署土壤墒情、空气温湿度、光照、CO2等传感器节点，常用ESP32等低功耗MCU采集数据。\n\n二、传输层\n棚内采用WiFi或LoRa组网，通过MQTT协议将数据上报到消息服务器，实现轻量级可靠传输。\n\n三、平台层\n数据入库后由规则引擎分析处理：越限告警、灌溉决策、设备联动控制。\n\n四、应用层\nWeb监测大屏、移动端管理、溯源系统为生产管理者和消费者提供数据服务。实际部署建议：传感器节点做防水处理，MQTT开启心跳保活，断线自动重连。"),
        ("智慧农业", "AI图像识别在作物病害诊断中的实践",
         "从数据采集、模型训练到田间部署的完整流程介绍，降低AI使用门槛。",
         "AI病害识别让『拍照识病』成为现实。\n\n一、数据准备\n采集不同发病阶段、不同光照条件下的病害图片，每种病害不少于500张，并进行数据增强。\n\n二、模型选择\n移动端推荐MobileNet等轻量模型；服务端可用ResNet、EfficientNet获得更高精度。\n\n三、训练与评估\n迁移学习可大幅减少训练成本，注意划分训练集/验证集，关注召回率避免漏诊。\n\n四、部署应用\n小程序拍照→上传服务端推理→返回病害类型、置信度和防治建议。实际应用中需定期用新数据迭代模型，并提示用户AI结果仅供参考。"),
    ]
    for cat, title, summary, content in knowledge:
        insert_knowledge(cat, title, summary, content)

    # ---- 农业新闻 ----
    news = [
        ("政策动态", "国家智慧农业行动计划发布：2027年农业生产信息化率目标超35%",
         "农业农村部部署智慧农业重点任务，物联网、大数据、AI将深度融入农业生产。",
         "近日，农业农村部印发智慧农业相关行动计划，提出到2027年全国农业生产信息化率达到35%以上。\n\n计划明确了五大重点任务：一是推进农业传感器与智能装备研发应用；二是建设农业大数据平台，打通生产、流通、监管数据链路；三是推广水肥一体化、智能温室等精准作业技术；四是培育智慧农业社会化服务组织；五是完善农产品质量安全追溯体系。\n\n业内专家指出，政策的落地将加速农业物联网终端的规模化部署，中小农户有望通过社会化服务低成本用上智慧农业技术。", 1),
        ("行业动态", "全国设施农业物联网设备安装量同比增长42%",
         "温室环境监测、智能灌溉设备成为增长最快的两个细分品类。",
         "据行业研究机构最新统计，本年度全国设施农业物联网设备安装量同比增长42%，其中温室环境监测设备与智能灌溉控制设备增速领跑。\n\n分析指出，设备成本持续下降是普及加速的主因：一套基础版温室监测终端（含温湿度、光照、土壤墒情传感器）价格已从五年前的数千元降至千元以内。\n\n同时，『按服务付费』的新模式正在兴起——农户无需购买设备，按年支付服务费即可获得监测、告警和灌溉决策服务，大幅降低了使用门槛。", 1),
        ("科技前沿", "AI病虫害识别准确率突破96%，手机拍照即可诊断",
         "基于深度学习的作物病害识别模型在多种作物上达到植保专家水平。",
         "国内某农业科研团队发布的新一代作物病害识别模型，在番茄、黄瓜、草莓等主要设施作物的50种常见病害上，识别准确率突破96%，达到高级植保专家水平。\n\n该模型采用改进的轻量化卷积神经网络，在保持精度的同时将模型体积压缩至15MB以内，可直接部署在手机端离线运行。农户拍照后1秒内即可获得病害类型、置信度和防治建议。\n\n目前该技术已在多个农业园区试点应用，帮助农户平均减少农药使用量15%以上。", 0),
        ("市场行情", "设施番茄产地收购价小幅上涨，优质果溢价明显",
         "本周设施番茄平均收购价环比上涨8%，精品果与普通果价差扩大至1.5倍。",
         "据主产区市场监测，本周设施番茄平均产地收购价较上周上涨约8%。\n\n价格分化趋势明显：糖度高、果形整齐的精品果收购价持续走强，与普通果的价差扩大至1.5倍。经销商普遍反映，稳定供应优质果的基地订单已排至下月。\n\n业内人士建议，种植户可通过水肥精准调控、增施有机肥、控制单穗留果数等措施提升果实品质，同时利用溯源系统打造品牌，获取品质溢价。", 0),
        ("政策动态", "农业农村部推进农产品质量安全追溯全覆盖",
         "规模生产主体将率先实现『带证上市』，扫码可查全程生产记录。",
         "农业农村部近期部署农产品质量安全追溯体系建设工作，要求规模生产主体率先实现承诺达标合格证『带证上市』。\n\n消费者扫描产品包装上的追溯二维码，即可查看产地环境、生产过程记录、投入品使用、检测报告等信息。\n\n多地已出台配套政策：对建设追溯系统的生产主体给予设备补贴，并将追溯实施情况纳入绿色食品、地理标志产品认证的加分项。智慧农业监测数据可直接对接追溯平台，实现生产记录自动归档。", 0),
        ("科技前沿", "低功耗LoRa传感器组网成本再降，大田监测进入平价时代",
         "单节点成本降至百元级，电池续航可达3年，适合大面积大田部署。",
         "随着LoRa芯片国产化率提升，大田环境监测节点成本已降至百元级别，配合低功耗设计，一节电池可续航3年以上。\n\n相比WiFi方案，LoRa在空旷大田的传输距离可达3-5公里，一个网关即可覆盖数百亩农田，特别适合墒情、气象等大田监测场景。\n\n在温室等近距离场景，WiFi+MQTT方案仍是性价比首选。专家建议根据种植场景混合组网：棚内WiFi、大田LoRa，数据统一汇聚到管理平台。", 0),
        ("行业动态", "多地试点『数字大棚』托管服务，农户手机即可管棚",
         "社会化服务组织接管设备运维，农户按棚付费享受全托式智慧管理。",
         "山东、河南等地近期试点『数字大棚』托管服务：由社会化服务组织统一安装监测与控制设备，农户按棚按年付费，即可通过手机查看棚内环境、远程控制卷帘和灌溉。\n\n试点农户反馈，托管后每日巡棚时间从2小时减少到20分钟，灌溉施肥更加精准，一季作物平均节水30%、增产10%以上。\n\n业内认为，『设备托管+数据服务』模式破解了农户『不会装、不会用、不会修』的难题，是智慧农业向中小农户普及的可行路径。", 0),
        ("市场行情", "有机肥替代化肥行动扩大试点，补贴力度加大",
         "果菜茶优势产区新增100个试点县，每亩最高补贴150元。",
         "农业农村部宣布扩大有机肥替代化肥试点范围，在果菜茶优势产区新增100个试点县，对施用有机肥的生产主体给予每亩最高150元补贴。\n\n试点县还配套建设有机肥质量追溯与效果监测体系，鼓励主体结合水肥一体化技术，实现有机肥与化肥的精准配施。\n\n专家提醒，有机肥替代需循序渐进：设施蔬菜建议基肥以腐熟有机肥为主、追肥以水溶肥为主，配合土壤墒情监测避免一次性施用过量造成烧根。", 0),
    ]
    for cat, title, summary, content, is_top in news:
        insert_news(cat, title, summary, content, is_top=is_top)

    # ---- 演示账号 ----
    seed_users()

    # ---- 站点内容默认值（about / faq / privacy / service）----
    seed_site_contents()


def seed_users():
    """播种演示账号（已存在则跳过），密码使用 PBKDF2 加盐哈希存储。"""
    import hashlib
    import uuid

    def _hash(password, salt=None):
        salt = salt or uuid.uuid4().hex[:16]
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000
        ).hex()
        return digest, salt

    accounts = [
        ("admin", "admin123", "系统管理员", "admin"),
        ("operator", "op123456", "张技术员", "operator"),
        ("viewer", "view123456", "李观察员", "viewer"),
    ]
    for username, password, display_name, role in accounts:
        if get_user_by_username(username):
            continue
        digest, salt = _hash(password)
        create_user(username, digest, salt, display_name, role)
        print("seed user:", username, "/", password, "(", role, ")")


def seed_site_contents():
    """播种站点默认内容（存在则覆盖为默认，便于 CMS 改前有基准）。"""
    defaults = [
        ("about", "关于我们",
         """
<div class="about-hero mb-4">
  <h3><i class="bi bi-flower1"></i> 让农业更智慧，让丰收更简单</h3>
  <p class="mt-3">
    AgriSense 智慧农业科技有限公司成立于 2010 年，专注于农业物联网、农业大数据与人工智能技术的研发与应用。
    我们为设施农业、大田种植、畜牧养殖等场景提供「感知-决策-控制-溯源」全链路数字化解决方案，
    核心产品涵盖环境监测终端、智能灌溉控制系统、农产品质量追溯平台与 AI 病害识别服务，
    帮助种植主体降本增效、提质增收，推动农业生产方式向数字化、智能化转型。
  </p>
</div>

<!-- 核心数据 -->
<div class="row g-3 mb-4">
  <div class="col-6 col-md-3"><div class="sensor-card num-card"><div class="num">14<span class="fs-6">年</span></div><div class="lbl">行业深耕经验</div></div></div>
  <div class="col-6 col-md-3"><div class="sensor-card num-card"><div class="num">12,000<span class="fs-6">+</span></div><div class="lbl">服务种植主体</div></div></div>
  <div class="col-6 col-md-3"><div class="sensor-card num-card"><div class="num">86<span class="fs-6">万亩</span></div><div class="lbl">累计覆盖种植面积</div></div></div>
  <div class="col-6 col-md-3"><div class="sensor-card num-card"><div class="num">35,000<span class="fs-6">+</span></div><div class="lbl">在线监测设备</div></div></div>
</div>

<div class="row g-3 mb-4">
  <!-- 发展历程 -->
  <div class="col-lg-6">
    <div class="sensor-card h-100">
      <h6 class="mb-3"><i class="bi bi-signpost-split"></i> 发展历程</h6>
      <div class="milestone"><div class="year">2010</div><div class="txt">公司成立，推出第一代温室环境监测终端，进入设施农业物联网领域</div></div>
      <div class="milestone"><div class="year">2012</div><div class="txt">智能灌溉控制系统上线，实现「监测+控制」闭环，服务面积突破 10 万亩</div></div>
      <div class="milestone"><div class="year">2014</div><div class="txt">发布农业大数据平台，接入设备破万台，获高新技术企业认定</div></div>
      <div class="milestone"><div class="year">2016</div><div class="txt">农产品溯源系统上线，率先实现「一批次一码」全程可追溯</div></div>
      <div class="milestone"><div class="year">2018</div><div class="txt">AI 病害图像识别服务发布，识别准确率达行业领先水平</div></div>
      <div class="milestone"><div class="year">2010 至今</div><div class="txt">构建「感知-决策-控制-溯源」全链路产品矩阵，持续服务农业数字化转型</div></div>
    </div>
  </div>

  <!-- 核心团队 + 荣誉 -->
  <div class="col-lg-6">
    <div class="sensor-card mb-3">
      <h6 class="mb-3"><i class="bi bi-people"></i> 核心团队</h6>
      <div class="row g-3">
        <div class="col-4 team-card"><div class="avatar"><i class="bi bi-person"></i></div><div class="fw-bold small">陈立农</div><div class="text-muted" style="font-size:11px">创始人 / CEO</div></div>
        <div class="col-4 team-card"><div class="avatar"><i class="bi bi-person"></i></div><div class="fw-bold small">王耘</div><div class="text-muted" style="font-size:11px">首席技术官</div></div>
        <div class="col-4 team-card"><div class="avatar"><i class="bi bi-person"></i></div><div class="fw-bold small">李穗</div><div class="text-muted" style="font-size:11px">农业科学家</div></div>
      </div>
      <p class="text-muted small mt-3 mb-0">
        团队由农业科学、物联网工程、人工智能领域的专家组成，研发人员占比超过 60%，
        与多所农业院校建立联合实验室，持续推动产学研成果转化。
      </p>
    </div>
    <div class="sensor-card">
      <h6 class="mb-2"><i class="bi bi-award"></i> 荣誉资质</h6>
      <div class="honor-item"><i class="bi bi-trophy"></i> 国家高新技术企业</div>
      <div class="honor-item"><i class="bi bi-trophy"></i> 农业物联网行业创新示范企业</div>
      <div class="honor-item"><i class="bi bi-trophy"></i> 智慧农业解决方案优秀服务商</div>
      <div class="honor-item"><i class="bi bi-trophy"></i> ISO9001 质量管理体系认证</div>
      <div class="honor-item"><i class="bi bi-trophy"></i> 30+ 项发明专利与软件著作权</div>
    </div>
  </div>
</div>
"""),
        ("faq", "问题解答",
         """<h6 style="color:#2e7d32;font-weight:700;margin-top:20px;"><i class="bi bi-box-seam"></i> 产品与功能</h6>
<p style="line-height:1.8;color:#555;"><strong>Q1：AgriSense 系统包含哪些核心功能？</strong><br>
系统提供环境监测（土壤墒情、温湿度、光照）、智能灌溉控制、规则引擎自动告警、执行器远程控制、农产品溯源、AI 病害识别、数据大屏可视化、移动端管理等完整功能，覆盖「感知-决策-控制-溯源」全链路。</p>
<p style="line-height:1.8;color:#555;"><strong>Q2：系统支持哪些作物和种植场景？</strong><br>
系统与作物种类无关，适用于设施大棚蔬菜、水果（番茄、黄瓜、草莓等）、大田作物及茶园、果园等场景。灌溉阈值、告警规则均可按作物自定义配置。</p>
<h6 style="color:#2e7d32;font-weight:700;margin-top:20px;"><i class="bi bi-cpu"></i> 设备安装与组网</h6>
<p style="line-height:1.8;color:#555;"><strong>Q3：大棚里没有 WiFi 信号怎么办？</strong><br>
提供三种方案：①棚区部署无线 AP 扩展 WiFi 覆盖；②采用 4G 网关直接回传数据；③远距离大田场景使用 LoRa 组网，单网关覆盖 3-5 公里。</p>
<h6 style="color:#2e7d32;font-weight:700;margin-top:20px;"><i class="bi bi-database"></i> 数据与服务</h6>
<p style="line-height:1.8;color:#555;"><strong>Q4：监测数据保存在哪里？会丢失吗？</strong><br>
数据默认保存在本地 SQLite 数据库，数据完全归您所有。建议定期备份数据库文件；规模化部署可升级为 MySQL/InfluxDB 并配置自动备份策略。</p>"""),
        ("privacy", "隐私政策与用户服务协议",
         """<h6 style="color:#1b5e20;font-weight:700;margin-top:22px;">一、总则</h6>
<p style="line-height:1.9;color:#555;">欢迎使用 AgriSense 智慧农业监测系统（以下简称「本系统」）。本隐私政策旨在说明我们在您使用本系统及相关服务时如何收集、使用、存储和保护您的信息。请您在使用本系统前仔细阅读并充分理解本政策的全部内容。</p>
<h6 style="color:#1b5e20;font-weight:700;margin-top:22px;">二、我们收集的信息</h6>
<ul style="line-height:1.9;color:#555;font-size:13.5px;">
  <li><strong>账户信息：</strong>您注册或使用系统时提供的姓名、联系方式等；</li>
  <li><strong>设备与生产数据：</strong>传感器采集的土壤墒情、温湿度、光照等环境监测数据，以及灌溉、农事操作等生产记录；</li>
  <li><strong>使用日志：</strong>系统运行日志、设备连接状态、操作记录等技术信息；</li>
  <li><strong>上传内容：</strong>您主动上传的作物图片（用于病害识别）、留言反馈内容等。</li>
</ul>
<h6 style="color:#1b5e20;font-weight:700;margin-top:22px;">三、信息的存储与保护</h6>
<p style="line-height:1.9;color:#555;">您的数据默认存储于您本地部署的服务器中，数据所有权完全归您所有。我们采取 PBKDF2 加盐哈希、HTTPS 传输、会话令牌鉴权等多重措施保障数据安全。</p>"""),
        ("service", "客服中心",
         """<p style="line-height:1.9;color:#555;">
我们提供<strong>7×24 小时</strong>的技术支持与售后服务。遇到任何问题，可通过以下方式联系我们：
</p>
<ul style="line-height:1.9;color:#555;font-size:13.5px;">
  <li><strong>服务热线：</strong>400-800-2010</li>
  <li><strong>官方微信：</strong>AgriSense2010</li>
  <li><strong>技术支持邮箱：</strong>support@agrisense.cn</li>
  <li><strong>人工客服时间：</strong>工作日 8:30 - 18:00</li>
</ul>
<h6 style="font-weight:700;color:#2e7d32;margin-top:18px;">服务承诺</h6>
<ul style="line-height:1.9;color:#555;font-size:13.5px;">
  <li><i class="bi bi-check-circle text-success me-1"></i> 工作日 2 小时内响应您的问题</li>
  <li><i class="bi bi-check-circle text-success me-1"></i> 设备故障上门维修，24-48 小时内到达</li>
  <li><i class="bi bi-check-circle text-success me-1"></i> 产品一年内免费质保，终身成本价维护</li>
  <li><i class="bi bi-check-circle text-success me-1"></i> 提供设备安装、数据迁移、使用培训一体化服务</li>
</ul>
<p style="font-size:12px;color:#999;margin-top:14px;">提示：您也可以使用左侧「在线留言」功能，客服将在 1 个工作日内与您联系。</p>"""),
        ("contact", "联系方式",
         """<p style="line-height:1.9;color:#555;">AgriSense 智慧农业科技有限公司<br>总部地址：智慧农业产业园 A3 栋<br>服务热线：400-800-2010<br>商务合作：contact@agrisense.cn</p>"""),
        ("terms", "服务条款",
         """<p style="line-height:1.9;color:#555;">请您在使用 AgriSense 服务前仔细阅读本条款。使用本系统即表示您同意本条款约定的全部内容。</p>
<h6 style="font-weight:700;color:#1b5e20;margin-top:18px;">一、服务说明</h6>
<p style="line-height:1.9;color:#555;">本系统提供智慧农业监测、智能灌溉、告警推送、溯源管理等功能，具体以产品实际交付为准。</p>"""),
    ]
    for key, title, content in defaults:
        upsert_site_content(key, title, content)
    print("seed site contents:", len(defaults), "entries")


if __name__ == "__main__":
    seed()
