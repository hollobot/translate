from __future__ import annotations

import hashlib
import re
import time

import requests


def baidu_translate(
    text: str,
    appid: str,
    secret: str,
    from_lang: str,
    to_lang: str,
    timeout: int = 8,
) -> str:
    """调用百度翻译 API，返回翻译结果字符串"""
    salt = str(int(time.time() * 1000))
    sign = hashlib.md5(f"{appid}{text}{salt}{secret}".encode("utf-8")).hexdigest()

    resp = requests.post(
        "http://api.fanyi.baidu.com/api/trans/vip/translate",
        params={
            "appid": appid,
            "q": text,
            "from": from_lang,
            "to": to_lang,
            "salt": salt,
            "sign": sign,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()

    if "error_code" in data:
        code = data.get("error_code", "")
        msg = data.get("error_msg", "未知错误")
        raise RuntimeError(f"百度翻译接口错误 {code}: {msg}")

    result = data.get("trans_result") or []
    if not result:
        raise RuntimeError("百度翻译返回为空")

    return "\n".join(item.get("dst", "") for item in result).strip()


def detect_lang_direction(text: str) -> tuple[str, str]:
    """检测文本语言方向：含中文则中->英，否则英->中"""
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh", "en"
    return "en", "zh"
