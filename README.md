# Smart Translate

基于百度翻译 API 的 Windows 桌面划词翻译工具。选中任意文本，按下快捷键，自动识别中英语言方向并在鼠标附近弹出翻译结果。

## 功能特性

- **划词翻译**：选中文本后按快捷键，无需切换窗口
- **自动识别语言**：含中文则译为英文，否则译为中文
- **悬浮弹窗**：结果跟随鼠标显示，点击外部或按 `ESC` 关闭
- **系统托盘**：常驻后台，右键图标可打开设置或退出，双击同样可打开设置
- **可视化设置**：支持在界面内修改 API 参数与快捷键，保存后立即生效，无需重启

## 环境要求

- Windows 10 / 11
- Python 3.9+

## 快速开始

**1. 安装依赖**

```bash
pip install -r requirements.txt
```

**2. 运行**

```bash
python main.py
```

首次运行时 `config.json` 不存在，程序会自动弹出设置窗口，填入 API 凭据后保存即可正常使用。

> 百度翻译 API 申请：[https://fanyi-api.baidu.com](https://fanyi-api.baidu.com)

## 使用方式

1. 用鼠标选中任意文本
2. 按下快捷键（默认 `Ctrl+Shift+T`）
3. 翻译结果在鼠标附近弹出
4. 点击弹窗外部或按 `ESC` 关闭

## 设置

右键托盘图标选择 **设置** 可打开配置窗口。

| 字段 | 说明 | 默认值 |
|------|------|--------|
| AppID | 百度翻译 AppID（必填） | — |
| 密钥 | 百度翻译密钥（必填） | — |
| 翻译热键 | 全局触发快捷键，点击录制框后按下组合键即可录入 | `ctrl+shift+t` |
| 超时 | API 请求超时时间（秒） | `8` |

配置保存在 `config.json`（脚本运行时位于项目根目录，打包后位于 exe 同级目录）。

## 打包为 exe

**安装打包依赖**（仅构建时需要）：

```bash
pip install pyinstaller pillow
```

**执行打包**：

```bash
python build.py
```

输出文件位于 `dist/SmartTranslate.exe`，打包产生的临时文件统一放在 `packaging/` 目录下。

> 若热键注册失败，请以**管理员身份**运行 exe。

## 项目结构

```
translate/
├── main.py             # 程序入口
├── build.py            # 打包脚本
├── requirements.txt
├── config.json         # 本地配置（自动生成，不提交到版本库）
└── core/               # 核心模块包
    ├── config.py       # 配置读写，自动适配脚本/exe 两种路径
    ├── translator.py   # 百度翻译 API 封装
    ├── winapi.py       # Windows API（剪贴板捕获、鼠标位置、键盘模拟）
    ├── popup.py        # 翻译结果悬浮弹窗
    ├── settings.py     # 设置窗口、热键录制控件、数字步进控件
    └── app.py          # 主控制器（托盘、翻译线程、弹窗调度）
```

## 运行时依赖

| 包 | 用途 |
|----|------|
| `PySide6` | GUI 框架 |
| `keyboard` | 全局热键注册 |
| `pyperclip` | 剪贴板读写 |
| `requests` | HTTP 请求 |
