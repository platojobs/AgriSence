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
         """
<div class="row g-3">
  <div class="col-lg-8">
    <div class="sensor-card">
      <h6 class="mb-3"><i class="bi bi-question-circle"></i> 常见问题解答</h6>

      <div class="faq-cat"><i class="bi bi-box-seam"></i> 产品与功能</div>
      <div class="accordion" id="faq1">
        <div class="accordion-item">
          <h2 class="accordion-header"><button class="accordion-button" data-bs-toggle="collapse" data-bs-target="#q1">AgriSense 系统包含哪些核心功能？</button></h2>
          <div id="q1" class="accordion-collapse collapse show" data-bs-parent="#faq1"><div class="accordion-body">系统提供环境监测（土壤墒情、温湿度、光照）、智能灌溉控制、规则引擎自动告警、执行器远程控制、农产品溯源、AI 病害识别、数据大屏可视化、移动端管理等完整功能，覆盖「感知-决策-控制-溯源」全链路。</div></div>
        </div>
        <div class="accordion-item">
          <h2 class="accordion-header"><button class="accordion-button collapsed" data-bs-toggle="collapse" data-bs-target="#q2">系统支持哪些作物和种植场景？</button></h2>
          <div id="q2" class="accordion-collapse collapse" data-bs-parent="#faq1"><div class="accordion-body">系统与作物种类无关，适用于设施大棚蔬菜、水果（番茄、黄瓜、草莓等）、大田作物及茶园、果园等场景。灌溉阈值、告警规则均可按作物自定义配置。</div></div>
        </div>
        <div class="accordion-item">
          <h2 class="accordion-header"><button class="accordion-button collapsed" data-bs-toggle="collapse" data-bs-target="#q3">病害识别的准确率如何？可以离线使用吗？</button></h2>
          <div id="q3" class="accordion-collapse collapse" data-bs-parent="#faq1"><div class="accordion-body">当前版本的病害识别为演示功能，基于内置病害知识库返回结果。生产环境可接入训练好的图像分类模型，常见病害识别准确率可达 90% 以上；模型经轻量化处理后支持移动端离线推理。AI 结果仅供参考，实际防治请咨询农技专家。</div></div>
        </div>
      </div>

      <div class="faq-cat"><i class="bi bi-cpu"></i> 设备安装与组网</div>
      <div class="accordion" id="faq2">
        <div class="accordion-item">
          <h2 class="accordion-header"><button class="accordion-button collapsed" data-bs-toggle="collapse" data-bs-target="#q4">传感器节点如何供电？续航多久？</button></h2>
          <div id="q4" class="accordion-collapse collapse" data-bs-parent="#faq2"><div class="accordion-body">棚内节点建议 220V 市电+适配器供电；无电源场景可选太阳能+锂电池方案。大田 LoRa 节点采用低功耗设计，一节电池可续航 2-3 年。</div></div>
        </div>
        <div class="accordion-item">
          <h2 class="accordion-header"><button class="accordion-button collapsed" data-bs-toggle="collapse" data-bs-target="#q5">大棚里没有 WiFi 信号怎么办？</button></h2>
          <div id="q5" class="accordion-collapse collapse" data-bs-parent="#faq2"><div class="accordion-body">提供三种方案：①棚区部署无线 AP 扩展 WiFi 覆盖；②采用 4G 网关直接回传数据；③远距离大田场景使用 LoRa 组网，单网关覆盖 3-5 公里。设备安装前我们会进行现场勘测并给出组网建议。</div></div>
        </div>
        <div class="accordion-item">
          <h2 class="accordion-header"><button class="accordion-button collapsed" data-bs-toggle="collapse" data-bs-target="#q6">土壤传感器应该埋多深？多久校准一次？</button></h2>
          <div id="q6" class="accordion-collapse collapse" data-bs-parent="#faq2"><div class="accordion-body">传感器应埋设在主要根系层，蔬菜建议 20-30cm 深度。电容式土壤传感器基本免校准，建议每季度检查探头接触是否良好、有无腐蚀，每年用烘干法比对一次数据确保精度。</div></div>
        </div>
        <div class="accordion-item">
          <h2 class="accordion-header"><button class="accordion-button collapsed" data-bs-toggle="collapse" data-bs-target="#q7">设备显示离线，如何排查？</button></h2>
          <div id="q7" class="accordion-collapse collapse" data-bs-parent="#faq2"><div class="accordion-body">按顺序排查：①检查设备供电是否正常；②检查 WiFi/网络连接（设备指示灯状态）；③确认 MQTT 服务（Mosquitto）是否运行；④查看后端日志是否收到数据。仍无法解决可联系客服远程协助。</div></div>
        </div>
      </div>

      <div class="faq-cat"><i class="bi bi-database"></i> 数据与服务</div>
      <div class="accordion" id="faq3">
        <div class="accordion-item">
          <h2 class="accordion-header"><button class="accordion-button collapsed" data-bs-toggle="collapse" data-bs-target="#q8">监测数据保存在哪里？会丢失吗？</button></h2>
          <div id="q8" class="accordion-collapse collapse" data-bs-parent="#faq3"><div class="accordion-body">数据默认保存在本地 SQLite 数据库，数据完全归您所有。建议定期备份数据库文件；规模化部署可升级为 MySQL/InfluxDB 并配置自动备份策略。</div></div>
        </div>
        <div class="accordion-item">
          <h2 class="accordion-header"><button class="accordion-button collapsed" data-bs-toggle="collapse" data-bs-target="#q9">历史数据可以导出吗？</button></h2>
          <div id="q9" class="accordion-collapse collapse" data-bs-parent="#faq3"><div class="accordion-body">可以。「历史分析」页面支持按时间范围查询并一键导出 CSV 文件，可直接用 Excel 打开进行进一步分析。</div></div>
        </div>
        <div class="accordion-item">
          <h2 class="accordion-header"><button class="accordion-button collapsed" data-bs-toggle="collapse" data-bs-target="#q10">多个大棚可以统一管理吗？</button></h2>
          <div id="q10" class="accordion-collapse collapse" data-bs-parent="#faq3"><div class="accordion-body">可以。系统支持多设备接入，每个大棚部署独立监测节点，在「设备管理」中统一查看状态，数据大屏可按地块/棚区展示所有监测点状态。</div></div>
        </div>
      </div>

      <div class="faq-cat"><i class="bi bi-headset"></i> 售后保障</div>
      <div class="accordion" id="faq4">
        <div class="accordion-item">
          <h2 class="accordion-header"><button class="accordion-button collapsed" data-bs-toggle="collapse" data-bs-target="#q11">设备质保政策是怎样的？</button></h2>
          <div id="q11" class="accordion-collapse collapse" data-bs-parent="#faq4"><div class="accordion-body">监测终端自签收之日起一年质保，非人为损坏免费维修或更换；人为损坏（如进水、摔坏）提供成本价维修。质保期外提供终身有偿维护服务。</div></div>
        </div>
        <div class="accordion-item">
          <h2 class="accordion-header"><button class="accordion-button collapsed" data-bs-toggle="collapse" data-bs-target="#q12">如何获得使用培训？</button></h2>
          <div id="q12" class="accordion-collapse collapse" data-bs-parent="#faq4"><div class="accordion-body">我们提供三种培训方式：①新用户远程视频指导（约 1 小时）；②每月线上公开课；③规模化基地客户可申请上门培训。详情请前往客服中心预约。</div></div>
        </div>
      </div>
    </div>
  </div>

  <!-- 侧边 -->
  <div class="col-lg-4">
    <div class="sensor-card mb-3">
      <h6 class="mb-3"><i class="bi bi-search"></i> 没找到答案？</h6>
      <p class="small text-muted">您可以通过以下方式获取进一步帮助：</p>
      <div class="d-grid gap-2">
        <a href="service.html" class="btn btn-success btn-sm"><i class="bi bi-headset"></i> 联系在线客服</a>
        <a href="knowledge.html" class="btn btn-outline-success btn-sm"><i class="bi bi-book"></i> 浏览农业知识库</a>
      </div>
    </div>
    <div class="sensor-card">
      <h6 class="mb-3"><i class="bi bi-telephone"></i> 快速联系</h6>
      <div class="small">
        <div class="mb-2"><i class="bi bi-telephone-fill text-success me-2"></i>400-800-2010</div>
        <div class="mb-2"><i class="bi bi-envelope-fill text-success me-2"></i>support@agrisense.cn</div>
        <div><i class="bi bi-clock-fill text-success me-2"></i>工作日 8:30 - 18:00</div>
      </div>
    </div>
  </div>
</div>
"""),
        ("privacy", "隐私政策与用户服务协议",
         """
<div class="sensor-card policy-body">
  <h5 class="fw-bold mb-1">隐私政策与用户服务协议</h5>
  <p class="text-muted small">更新日期：2010年8月 · 生效日期：2010年8月</p>

  <h6 id="s1">一、总则</h6>
  <p>欢迎使用 AgriSense 智慧农业监测系统（以下简称「本系统」）。本隐私政策旨在说明我们在您使用本系统及相关服务时如何收集、使用、存储和保护您的信息。请您在使用本系统前仔细阅读并充分理解本政策的全部内容。一旦您使用本系统，即表示您已同意本政策的约定。</p>

  <h6 id="s2">二、我们收集的信息</h6>
  <p>为向您提供智慧农业服务，我们可能收集以下信息：</p>
  <ul>
    <li><strong>账户信息：</strong>您注册或使用系统时提供的姓名、联系方式等；</li>
    <li><strong>设备与生产数据：</strong>您部署的传感器采集的土壤墒情、温湿度、光照等环境监测数据，以及灌溉、农事操作等生产记录；</li>
    <li><strong>使用日志：</strong>系统运行日志、设备连接状态、操作记录等技术信息；</li>
    <li><strong>上传内容：</strong>您主动上传的作物图片（用于病害识别）、留言反馈内容等。</li>
  </ul>

  <h6 id="s3">三、信息的使用</h6>
  <p>我们仅在以下目的范围内使用收集的信息：</p>
  <ul>
    <li>提供环境监测、智能灌溉、告警推送等核心服务；</li>
    <li>生成生产分析报表与农产品溯源记录；</li>
    <li>改进产品功能、优化算法模型（数据经匿名化处理）；</li>
    <li>响应您的客服请求与售后支持。</li>
  </ul>
  <p>我们不会将您的生产数据用于任何与您无关的商业用途。</p>

  <h6 id="s4">四、信息的存储与保护</h6>
  <p>您的数据默认存储于您本地部署的服务器中，数据所有权完全归您所有。我们采取以下措施保障数据安全：</p>
  <ul>
    <li>传输过程采用加密通道，防止数据被窃取或篡改；</li>
    <li>严格的访问权限控制，仅授权人员可接触系统运维数据；</li>
    <li>建议并协助您建立定期备份机制，防止数据意外丢失。</li>
  </ul>

  <h6 id="s5">五、信息的共享与披露</h6>
  <p>我们不会向任何第三方出售您的个人信息与生产数据。仅在以下情形下可能共享或披露：</p>
  <ul>
    <li>获得您的明确授权同意；</li>
    <li>根据法律法规、司法机关或行政机关的强制性要求；</li>
    <li>农产品溯源场景中，您主动选择向消费者公开的生产过程信息。</li>
  </ul>

  <h6 id="s6">六、您的权利</h6>
  <p>您对自己的数据享有以下权利：</p>
  <ul>
    <li><strong>访问与导出：</strong>可随时通过系统查询并导出历史数据（CSV 格式）；</li>
    <li><strong>更正：</strong>可更正账户信息与生产记录；</li>
    <li><strong>删除：</strong>可删除农事日志、反馈留言等个人提交的内容；</li>
    <li><strong>注销：</strong>可联系我们停止使用服务并删除相关数据。</li>
  </ul>

  <h6 id="s7">七、未成年人保护</h6>
  <p>本系统面向农业生产经营者提供服务，不面向未成年人。我们不会有意收集未成年人的个人信息。如发现误收集，将立即删除相关数据。</p>

  <h6 id="s8">八、政策更新</h6>
  <p>随着产品功能的发展，本政策可能适时更新。更新后的政策将在本页面公布，重大变更将通过系统内通知的方式提示您。建议您定期查阅本页面以了解最新政策。</p>

  <h6 id="s9">九、联系我们</h6>
  <p>如您对本政策或个人信息保护有任何疑问、意见或建议，可通过以下方式与我们联系：</p>
  <ul>
    <li>客服热线：400-800-2010</li>
    <li>联系邮箱：privacy@agrisense.cn</li>
    <li>在线留言：前往「客服中心」提交您的问题</li>
  </ul>
  <p>我们将在收到您的请求后 15 个工作日内予以回复。</p>
</div>
"""),
        ("service", "客服中心",
         """
<div class="sensor-card h-100">
  <h6 class="mb-2"><i class="bi bi-shield-check"></i> 服务承诺</h6>
  <div class="promise-item"><i class="bi bi-lightning-charge"></i><div><div class="t">2 小时快速响应</div><div class="d">工作时间内提交的故障报修，2 小时内响应并给出处理方案</div></div></div>
  <div class="promise-item"><i class="bi bi-tools"></i><div><div class="t">免费上门调试</div><div class="d">新装设备提供首次免费上门安装与调试服务</div></div></div>
  <div class="promise-item"><i class="bi bi-arrow-repeat"></i><div><div class="t">一年质保换新</div><div class="d">监测终端一年内非人为损坏免费维修或更换</div></div></div>
  <div class="promise-item"><i class="bi bi-mortarboard"></i><div><div class="t">免费技术培训</div><div class="d">定期举办线上培训，帮助用户掌握系统全部功能</div></div></div>
  <div class="promise-item"><i class="bi bi-headset"></i><div><div class="t">专属客户成功经理</div><div class="d">规模化基地客户配备一对一客户成功经理全程跟进</div></div></div>
</div>
"""),
        ("contact", "联系方式",
         """
<div class="cs-hero">
  <h4><i class="bi bi-geo-alt-fill"></i> 欢迎联系 AgriSense</h4>
  <p>我们随时准备为您提供智慧农业相关的咨询、方案设计与技术支持。请通过以下方式联系我们。</p>
</div>

<div class="row g-3 mb-4">
  <div class="col-md-6 col-lg-3">
    <div class="cs-card"><div class="ico"><i class="bi bi-geo-alt-fill"></i></div><div><div class="t">总部地址</div><div class="v">智慧农业产业园 A3 栋<br/>上海市浦东新区科苑路 88 号</div></div></div>
  </div>
  <div class="col-md-6 col-lg-3">
    <div class="cs-card"><div class="ico"><i class="bi bi-telephone-fill"></i></div><div><div class="t">服务热线</div><div class="v">400-800-2010<br/>工作日 8:30 - 18:00</div></div></div>
  </div>
  <div class="col-md-6 col-lg-3">
    <div class="cs-card"><div class="ico"><i class="bi bi-envelope-fill"></i></div><div><div class="t">邮件联系</div><div class="v">技术支持 support@agrisense.cn<br/>商务合作 contact@agrisense.cn</div></div></div>
  </div>
  <div class="col-md-6 col-lg-3">
    <div class="cs-card"><div class="ico"><i class="bi bi-wechat"></i></div><div><div class="t">官方微信</div><div class="v">公众号：AgriSense2010<br/>微信扫描下方二维码关注</div></div></div>
  </div>
</div>
"""),
        ("terms", "服务条款",
         """
<div class="sensor-card policy-body">
  <h5 class="fw-bold mb-1">AgriSense 服务条款</h5>
  <p class="text-muted small">更新日期：2010年8月 · 生效日期：2010年8月</p>

  <h6 id="t1">一、服务说明</h6>
  <p>AgriSense 智慧农业科技有限公司（以下简称「我们」）提供的智慧农业监测系统（以下简称「本系统」）包括但不限于环境监测、智能灌溉、告警推送、溯源管理、病害识别等功能模块。本系统的具体功能与服务内容以产品实际交付为准，我们保留随时调整的权利。</p>

  <h6 id="t2">二、账号注册与使用</h6>
  <p>您在使用本系统前需注册账号，注册时应提供真实、准确的信息。您应妥善保管账号与密码，因您保管不当造成的损失由您自行承担。您的账号仅限本人使用，不得转借、出租或出售给第三方。</p>

  <h6 id="t3">三、使用规范</h6>
  <p>您在使用本系统时应遵守以下规范：</p>
  <ul>
    <li>不得利用本系统从事任何违反法律法规的活动；</li>
    <li>不得对本系统进行反编译、逆向工程或恶意攻击；</li>
    <li>不得干扰或破坏其他用户的正常使用；</li>
    <li>应妥善保管您部署的硬件设备，定期维护确保数据采集质量。</li>
  </ul>

  <h6 id="t4">四、知识产权</h6>
  <p>本系统的全部知识产权（包括但不限于软件、界面设计、算法、文档）归我们所有，受相关法律法规保护。未经我们书面授权，您不得以任何形式复制、传播、修改或用于商业用途。</p>

  <h6 id="t5">五、免责声明</h6>
  <p>在法律允许的范围内，我们对以下情况不承担责任：</p>
  <ul>
    <li>因不可抗力（包括但不限于自然灾害、电力中断、网络故障）造成的服务中断或数据损失；</li>
    <li>AI 病害识别等智能分析功能的结果仅供参考，实际防治请咨询农技专家；</li>
    <li>因您未及时维护硬件设备或操作不当导致的数据不准确。</li>
  </ul>

  <h6 id="t6">六、服务变更与中断</h6>
  <p>我们有权根据业务发展需要对服务内容进行调整、升级或终止。对于重要变更，我们将通过系统内通知的方式提前告知。服务中断期间我们将尽力减少对用户的影响。</p>

  <h6 id="t7">七、终止条款</h6>
  <p>如您违反本服务条款的约定，我们有权单方面终止向您提供服务，并注销您的账号。您也可主动申请终止使用，终止后您的数据将按约定进行处理。</p>

  <h6 id="t8">八、适用法律</h6>
  <p>本服务条款的订立、执行与解释均适用中华人民共和国法律。因本条款引起的争议，双方应友好协商解决；协商不成的，任何一方均有权向我们所在地有管辖权的人民法院提起诉讼。</p>

  <h6 id="t9">九、联系我们</h6>
  <p>如您对本服务条款有任何疑问或建议，可通过以下方式与我们联系：</p>
  <ul>
    <li>客服热线：400-800-2010</li>
    <li>联系邮箱：legal@agrisense.cn</li>
    <li>在线留言：前往「客服中心」提交您的问题</li>
  </ul>
  <p>我们将在收到您的请求后 15 个工作日内予以回复。</p>
</div>
"""),
    ]
    for key, title, content in defaults:
        upsert_site_content(key, title, content)
    print("seed site contents:", len(defaults), "entries")


if __name__ == "__main__":
    seed()
