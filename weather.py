# -*- coding: utf-8 -*-
"""每日英国天气推送 —— 云端版本 (GitHub Actions)

仅使用 Python 标准库，无需安装任何依赖。
从 Open-Meteo 获取 7 个英国区域的天气，构建飞书互动卡片，
通过 Webhook 推送到"英国天气"外部群。

Webhook 地址从环境变量 FEISHU_WEBHOOK_URL 读取。
"""
import os
import sys
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta

import os
import sys
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta

# Windows 控制台默认 GBK 编码，强制设为 UTF-8 避免中文/emoji 输出报错
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# ---------- 配置 ----------
REGIONS = [
    ("伦敦及英格兰东南部", 51.5074, -0.1278),
    ("英格兰北部", 53.4808, -2.2426),
    ("英格兰中部", 52.4862, -1.8904),
    ("英格兰东部", 52.6398, 1.2969),
    ("英格兰西南部", 51.4545, -2.5879),
    ("苏格兰", 55.9533, -3.1883),
    ("威尔士", 51.4816, -3.1791),
]

WMO_DESC = {
    0: "晴", 1: "晴间多云", 2: "多云", 3: "阴", 45: "有雾", 48: "雾凇",
    51: "毛毛雨", 53: "毛毛雨", 55: "较强毛毛雨", 56: "冻毛毛雨", 57: "较强冻毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨", 66: "冻雨", 67: "较强冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "阵雪",
    80: "阵雨", 81: "较强阵雨", 82: "暴雨", 85: "阵雪", 86: "较强阵雪",
    95: "雷阵雨", 96: "雷阵雨伴冰雹", 99: "强雷阵雨伴冰雹",
}

WMO_EMOJI = {
    0: "☀️", 1: "🌤️", 2: "⛅", 3: "☁️", 45: "🌫️", 48: "🌫️",
    51: "🌦️", 53: "🌦️", 55: "🌧️", 56: "🌧️", 57: "🌧️",
    61: "🌦️", 63: "🌧️", 65: "🌧️", 66: "🌧️", 67: "🌧️",
    71: "🌨️", 73: "🌨️", 75: "❄️", 77: "🌨️",
    80: "🌦️", 81: "🌧️", 82: "⛈️", 85: "🌨️", 86: "❄️",
    95: "⛈️", 96: "⛈️", 99: "⛈️",
}


def http_get_json(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "uk-weather-cloud/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_post_json(url, payload, timeout=20):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json; charset=utf-8"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_region(name, lat, lon):
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,sunrise,sunset",
        "timezone": "Europe/London",
        "forecast_days": 1,
    }
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)
    d = http_get_json(url)

    code = int(d["current"]["weather_code"])
    desc = WMO_DESC.get(code, "未知")
    emoji = WMO_EMOJI.get(code, "❓")
    cur_t = round(d["current"]["temperature_2m"])
    max_t = round(d["daily"]["temperature_2m_max"][0])
    min_t = round(d["daily"]["temperature_2m_min"][0])
    hum = round(d["current"]["relative_humidity_2m"])
    wind = round(d["current"]["wind_speed_10m"])
    precip = round(d["daily"]["precipitation_sum"][0], 1)
    sunrise = d["daily"]["sunrise"][0][11:16]
    sunset = d["daily"]["sunset"][0][11:16]

    return {
        "name": name,
        "weather": f"{emoji} {desc}",
        "cur_temp": f"{cur_t}°C",
        "temp_range": f"{max_t}°C / {min_t}°C",
        "humidity": f"湿度 {hum}%",
        "wind": f"风速 {wind}km/h",
        "precip": f"降水 {precip}mm",
        "sun": f"日出 {sunrise} / 日落 {sunset}",
    }


def build_card(regions_data):
    uk_tz = timezone(timedelta(hours=1))  # BST
    today = datetime.now(uk_tz).strftime("%Y-%m-%d")

    elements = []
    for i, r in enumerate(regions_data):
        if i > 0:
            elements.append({"tag": "hr"})
        content = (
            f"**{r['name']}** {r['weather']}\n"
            f"当前 {r['cur_temp']} · 今日 {r['temp_range']}\n"
            f"{r['humidity']} · {r['wind']} · {r['precip']} · {r['sun']}"
        )
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": content}})

    card = {
        "schema": "2.0",
        "config": {"update_multi": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"每日英国天气 · {today}"},
            "template": "blue",
        },
        "body": {"elements": elements},
    }
    return {"msg_type": "interactive", "card": card}


def main():
    webhook_url = os.environ.get("FEISHU_WEBHOOK_URL")
    if not webhook_url:
        print("错误: 未设置环境变量 FEISHU_WEBHOOK_URL", file=sys.stderr)
        sys.exit(1)

    print("正在获取英国天气数据...")
    regions_data = []
    for name, lat, lon in REGIONS:
        try:
            r = fetch_region(name, lat, lon)
            regions_data.append(r)
            print(f"  ✓ {name}: {r['weather']} 当前{r['cur_temp']}")
        except Exception as e:
            print(f"  ✗ {name}: 获取失败 - {e}", file=sys.stderr)
            regions_data.append({
                "name": name, "weather": "❓ 获取失败",
                "cur_temp": "N/A", "temp_range": "N/A",
                "humidity": "N/A", "wind": "N/A", "precip": "N/A", "sun": "N/A",
            })

    print("正在发送到飞书群...")
    payload = build_card(regions_data)
    try:
        resp = http_post_json(webhook_url, payload)
        if resp.get("code") == 0:
            print("✅ 发送成功！")
        else:
            print(f"❌ 发送失败: code={resp.get('code')} msg={resp.get('msg')}", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"❌ 请求失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
