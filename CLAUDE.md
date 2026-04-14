# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 运行方式

```bash
# 安装依赖
pip install -r requirements.txt

# 启动应用
python main.py
```

运行前需要 `config.json` 中填写有效的百度翻译 API `appid` 和 `secret`。

## 架构概览

单文件应用 (`main.py`)，Windows 专用桌面工具。

**核心流程：**  
用户选中文本 → 按热键 → 后台线程通过剪贴板捕获文本 → 调用百度翻译 API → PySide6 无边框弹窗展示结果

**主要类/函数：**

| 组件 | 职责 |
|------|------|
| `TranslateHotkeyApp` | 主控制器：热键注册、线程管理、弹窗定位 |
| `TranslatePopup` | PySide6 无边框悬浮窗，跟随鼠标显示，支持动态尺寸 |
| `UiBridge` | Qt Signal 桥接，用于从后台线程安全更新 UI |
| `baidu_translate()` | 百度翻译 API 调用，含 MD5 签名 |
| `detect_lang_direction()` | 检测中文字符决定翻译方向（中→英 或 英→中） |
| `capture_selected_text()` | 依次尝试 4 种复制策略，通过哨兵值检测剪贴板变化 |

**关键设计：**
- 弹窗使用 `Qt.Tool | Qt.WA_ShowWithoutActivating`，避免抢占焦点导致复制失败
- 复制策略：keyboard 库 → WinAPI SendInput(Ctrl+C) → Ctrl+Insert → WinAPI SendInput(Ctrl+Insert)，多轮回退提升兼容性（微信等）
- `threading.Lock` 防止热键连击导致并发请求
- 翻译请求在 daemon 线程中执行，热键回调不阻塞

## 配置项（config.json）

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `appid` | 百度翻译 appid（必填） | — |
| `secret` | 百度翻译密钥（必填） | — |
| `hotkey` | 全局热键 | `ctrl+shift+t` |
| `timeout` | API 超时秒数 | `8` |

## 注意事项

- **仅支持 Windows**：大量使用 `ctypes.windll`、`wintypes`、`GetAsyncKeyState`
- `Baidu_Text_transAPI.py` 是百度官方参考示例，不被 `main.py` 引用，勿修改
- 修改复制捕获逻辑时注意哨兵值机制和多轮重试顺序
