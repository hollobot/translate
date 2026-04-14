from __future__ import annotations

import json
import sys
from pathlib import Path

# 打包为 exe 后 __file__ 指向临时解压目录，config.json 应放在 exe 同级目录
if getattr(sys, "frozen", False):
    CONFIG_PATH = Path(sys.executable).parent / "config.json"
else:
    CONFIG_PATH = Path(__file__).parent.parent / "config.json"

_DEFAULTS: dict = {
    "hotkey":  "ctrl+shift+t",
    "timeout": 8,
}


def load_config() -> dict:
    """
    加载配置文件。
    若文件不存在（首次运行），返回含空凭据的默认配置，
    调用方需检查 appid/secret 是否为空并引导用户配置。
    """
    if not CONFIG_PATH.exists():
        return {"appid": "", "secret": "", **_DEFAULTS}

    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        cfg = json.load(f)

    # 空值（含空字符串）均回退到默认值，防止启动时传空字符串给 keyboard 库
    for key, default in _DEFAULTS.items():
        if not cfg.get(key):
            cfg[key] = default

    return cfg


def save_config(cfg: dict) -> None:
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
