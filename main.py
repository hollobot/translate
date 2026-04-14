import hashlib
import ctypes
import json
import re
import threading
import time
from pathlib import Path
from ctypes import wintypes

import keyboard
import pyperclip
import requests
from PySide6.QtCore import QEvent, QObject, QPoint, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QFont, QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QLabel,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


CONFIG_PATH = Path(__file__).with_name("config.json")

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
VK_CONTROL = 0x11
VK_C = 0x43
VK_INSERT = 0x2D
VK_LBUTTON = 0x01
VK_ESCAPE = 0x1B
ULONG_PTR = (
    ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong
)


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("ki", KEYBDINPUT)]


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            "未找到 config.json，请先根据 config.example.json 创建配置文件。"
        )

    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        cfg = json.load(f)

    required = ["appid", "secret"]
    missing = [k for k in required if not cfg.get(k)]
    if missing:
        raise ValueError(f"配置缺少必要字段: {', '.join(missing)}")

    cfg.setdefault("hotkey", "ctrl+shift+t")
    cfg.setdefault("timeout", 8)
    return cfg


def baidu_translate(
    text: str,
    appid: str,
    secret: str,
    from_lang: str,
    to_lang: str,
    timeout: int = 8,
) -> str:
    salt = str(int(time.time() * 1000))
    sign_raw = f"{appid}{text}{salt}{secret}"
    sign = hashlib.md5(sign_raw.encode("utf-8")).hexdigest()

    # 对齐百度官方示例：使用 /api/trans/vip/translate + POST + form 参数
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
        msg = data.get("error_msg", "未知错误")
        code = data.get("error_code", "")
        raise RuntimeError(f"百度翻译接口错误 {code}: {msg}")

    result = data.get("trans_result") or []
    if not result:
        raise RuntimeError("百度翻译返回为空")

    return "\n".join(item.get("dst", "") for item in result).strip()


def detect_lang_direction(text: str) -> tuple[str, str]:
    # 命中中文字符时按中->英翻译，否则按英->中翻译
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh", "en"
    return "en", "zh"


class UiBridge(QObject):
    update_result = Signal(str, str, bool)
    show_loading = Signal()


class TranslatePopup(QWidget):
    def __init__(self) -> None:
        super().__init__(None)
        self.min_width = 420
        self.max_width = 720
        self.min_height = 130
        self.max_height = 520
        self.loading_base = "翻译中"
        self.loading_step = 0

        # 使用 Tool 无激活浮窗，避免在复制选中文本前抢占焦点
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.resize(self.min_width, self.min_height)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setStyleSheet("background: transparent;")

        self.container = QFrame(self)
        self.container.setObjectName("card")

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(15, 23, 42, 95))
        self.container.setGraphicsEffect(shadow)

        self.title_label = QLabel("Smart Translate")
        self.title_label.setStyleSheet(
            "color: #0f172a; font-size: 13px; font-weight: 700; letter-spacing: 0.4px;"
        )

        self.meta_label = QLabel("ready")
        self.meta_label.setStyleSheet(
            "color: #475569; font-size: 11px; font-weight: 600;"
            "background: rgba(148, 163, 184, 0.14); border-radius: 10px;"
            "padding: 2px 8px;"
        )

        # QTextEdit 只读模式仍支持鼠标选中文本和 Ctrl+C
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_edit.setStyleSheet(
            "QTextEdit { background: rgba(255, 255, 255, 0.86);"
            "border: 1px solid rgba(148, 163, 184, 0.22);"
            "border-radius: 10px; color: #0f172a; padding: 10px 12px;"
            "selection-background-color: #bfdbfe; line-height: 1.6; }"
            "QScrollBar:vertical {"
            "background: transparent; width: 10px; margin: 8px 2px 8px 2px;"
            "}"
            "QScrollBar::handle:vertical {"
            "background: rgba(100, 116, 139, 0.45); min-height: 30px; border-radius: 5px;"
            "}"
            "QScrollBar::handle:vertical:hover {"
            "background: rgba(59, 130, 246, 0.62);"
            "}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {"
            "height: 0px;"
            "}"
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {"
            "background: transparent;"
            "}"
        )
        self.text_edit.setFont(QFont("Microsoft YaHei UI", 11))
        self.text_edit.installEventFilter(self)

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(14, 12, 14, 14)
        content_layout.setSpacing(8)
        content_layout.addWidget(self.title_label)
        content_layout.addWidget(self.meta_label, alignment=Qt.AlignLeft)
        content_layout.addWidget(self.text_edit)
        self.container.setLayout(content_layout)

        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(self.container)
        self.setLayout(root_layout)

        self.loading_timer = QTimer(self)
        self.loading_timer.setInterval(260)
        self.loading_timer.timeout.connect(self.update_loading_dots)

    def show_shell(self) -> None:
        # 先展示卡片框架，再启动 loading 动画，提升可感知的响应速度
        self.stop_loading()
        self.set_error_style(False)
        self.meta_label.setText("ready")
        self.text_edit.setPlainText("\n")
        self.update_geometry_for_text("正在准备翻译")

    def eventFilter(self, watched, event):
        if watched is self.text_edit and event.type() == QEvent.KeyPress:
            key_event = event
            if key_event.key() == Qt.Key_Escape:
                self.hide()
                return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)

    def set_error_style(self, is_error: bool) -> None:
        if is_error:
            border = "rgba(252, 165, 165, 0.9)"
            title = "#7f1d1d"
            chip = "rgba(248, 113, 113, 0.2)"
            card_bg = (
                "qlineargradient(x1:0, y1:0, x2:1, y2:1,"
                " stop:0 rgba(255, 241, 242, 0.98),"
                " stop:1 rgba(255, 255, 255, 0.98))"
            )
        else:
            border = "rgba(147, 197, 253, 0.9)"
            title = "#0f172a"
            chip = "rgba(59, 130, 246, 0.16)"
            card_bg = (
                "qlineargradient(x1:0, y1:0, x2:1, y2:1,"
                " stop:0 rgba(239, 246, 255, 0.97),"
                " stop:1 rgba(255, 255, 255, 0.98))"
            )

        self.container.setStyleSheet(
            "QFrame#card {"
            f"background: {card_bg};"
            f"border: 1px solid {border};"
            "border-radius: 16px;"
            "}"
        )
        self.title_label.setStyleSheet(
            f"font-size: 13px; font-weight: 700; letter-spacing: 0.4px;color: {title};"
        )
        self.meta_label.setStyleSheet(
            "color: #475569; font-size: 11px; font-weight: 600;"
            f"background: {chip}; border-radius: 10px; padding: 2px 8px;"
        )

    def update_geometry_for_text(self, text: str) -> None:
        text_len = max(1, len(text))
        # 按文本量动态调整弹窗宽高，最小尺寸约可容纳 50 字左右
        target_width = min(self.max_width, max(self.min_width, 360 + text_len * 3))
        content_width = target_width - 40

        doc = self.text_edit.document()
        doc.setTextWidth(content_width)
        doc_height = int(doc.size().height()) + 14

        target_height = min(
            self.max_height,
            max(self.min_height, doc_height + self.meta_label.sizeHint().height() + 64),
        )
        self.resize(target_width, target_height)

    def start_loading(self) -> None:
        self.loading_step = 0
        self.meta_label.setText("processing")
        self.set_error_style(False)
        loading_text = "正在检测并翻译选中文本"
        self.text_edit.setPlainText(loading_text)
        self.update_geometry_for_text(loading_text)
        self.loading_timer.start()

    def stop_loading(self) -> None:
        self.loading_timer.stop()

    def update_loading_dots(self) -> None:
        self.loading_step = (self.loading_step + 1) % 4
        dots = "." * self.loading_step
        self.text_edit.setPlainText(f"正在检测并翻译选中文本{dots}")

    def set_content(self, text: str, lang_pair: str, is_error: bool = False) -> None:
        self.stop_loading()
        self.set_error_style(is_error)
        self.meta_label.setText(lang_pair or "")
        self.text_edit.setPlainText(text)
        self.update_geometry_for_text(text)


class TranslateHotkeyApp:
    def __init__(self, config: dict) -> None:
        self.config = config
        self.lock = threading.Lock()
        self.qt_app = QApplication([])
        self.popup = TranslatePopup()
        self.bridge = UiBridge()
        self.bridge.update_result.connect(self.show_result)
        self.bridge.show_loading.connect(self.show_loading)

        # 轮询鼠标/ESC，全局实现点击外部关闭和 Esc 关闭
        self.state_timer = QTimer()
        self.state_timer.setInterval(35)
        self.state_timer.timeout.connect(self.check_popup_state)
        self.prev_left_down = False
        self.prev_esc_down = False

    def get_cursor_pos(self):
        pt = wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y

    def get_screen_size(self):
        user32 = ctypes.windll.user32
        return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)

    def show_result(
        self, text: str, lang_pair: str = "", is_error: bool = False
    ) -> None:
        self.popup.set_content(text, lang_pair, is_error)
        self.show_popup_near_cursor(bring_front=True)

    def show_loading(self) -> None:
        self.popup.show_shell()
        self.show_popup_near_cursor(bring_front=False)
        # 先显示浮窗壳，再启动 loading 动画
        QTimer.singleShot(90, self.popup.start_loading)

    def show_popup_near_cursor(self, bring_front: bool) -> None:
        self.popup.adjustSize()

        mouse_x, mouse_y = self.get_cursor_pos()
        screen_w, screen_h = self.get_screen_size()

        # 弹窗跟随鼠标显示，同时限制在屏幕可视区域内
        x = min(max(10, mouse_x + 12), max(10, screen_w - self.popup.width() - 10))
        y = min(max(10, mouse_y + 14), max(10, screen_h - self.popup.height() - 10))

        self.popup.move(x, y)
        self.popup.show()
        if not self.state_timer.isActive():
            self.state_timer.start()
        if bring_front:
            self.popup.raise_()

    def check_popup_state(self) -> None:
        if not self.popup.isVisible():
            return

        left_down = bool(ctypes.windll.user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)
        esc_down = bool(ctypes.windll.user32.GetAsyncKeyState(VK_ESCAPE) & 0x8000)

        # 按下 ESC 时关闭浮窗
        if esc_down and not self.prev_esc_down:
            self.popup.hide()

        # 点击浮窗外部时关闭浮窗
        if left_down and not self.prev_left_down:
            x, y = self.get_cursor_pos()
            if not self.popup.geometry().contains(QPoint(x, y)):
                self.popup.hide()

        self.prev_left_down = left_down
        self.prev_esc_down = esc_down

    def translate_selected_text(self) -> None:
        try:
            selected_text = self.capture_selected_text()

            if not selected_text:
                self.bridge.update_result.emit("未检测到选中文本", "复制失败", True)
                return

            from_lang, to_lang = detect_lang_direction(selected_text)
            lang_pair = f"{from_lang} -> {to_lang}"

            translated = baidu_translate(
                selected_text,
                self.config["appid"],
                self.config["secret"],
                from_lang,
                to_lang,
                int(self.config.get("timeout", 8)),
            )
            self.bridge.update_result.emit(translated, lang_pair, False)
        except Exception as e:
            self.bridge.update_result.emit(f"翻译失败: {e}", "接口异常", True)
        finally:
            self.lock.release()

    def capture_selected_text(self) -> str:
        original_clip = pyperclip.paste()
        sentinel = f"__translate_sentinel_{time.time_ns()}__"

        try:
            # 先写入哨兵值，避免把旧剪贴板内容误判为新选中文本
            pyperclip.copy(sentinel)
            time.sleep(0.03)

            # 微信等应用里热键释放和复制入剪贴板可能更慢，分轮次回退可提升命中率
            time.sleep(0.22)
            triggers = (
                self.trigger_copy_by_keyboard,
                self.trigger_copy_by_winapi,
                self.trigger_copy_by_ctrl_insert,
                self.trigger_copy_by_winapi_ctrl_insert,
            )
            for _ in range(2):
                for trigger_copy in triggers:
                    trigger_copy()
                    if self.wait_clipboard_changed(sentinel, timeout=1.0):
                        return (pyperclip.paste() or "").strip()
                time.sleep(0.06)
            return ""
        finally:
            # 无论成功与否都恢复原剪贴板，减少对用户操作干扰
            pyperclip.copy(original_clip)

    def wait_clipboard_changed(self, sentinel: str, timeout: float) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            current = (pyperclip.paste() or "").strip()
            if current and current != sentinel:
                return True
            time.sleep(0.03)
        return False

    def trigger_copy_by_keyboard(self) -> None:
        keyboard.press_and_release("ctrl+c")

    def trigger_copy_by_ctrl_insert(self) -> None:
        keyboard.press_and_release("ctrl+insert")

    def trigger_copy_by_winapi(self) -> None:
        self.send_ctrl_combo(VK_C)

    def trigger_copy_by_winapi_ctrl_insert(self) -> None:
        self.send_ctrl_combo(VK_INSERT)

    def send_ctrl_combo(self, vk_code: int) -> None:
        inputs = (
            INPUT(INPUT_KEYBOARD, KEYBDINPUT(VK_CONTROL, 0, 0, 0, 0)),
            INPUT(INPUT_KEYBOARD, KEYBDINPUT(vk_code, 0, 0, 0, 0)),
            INPUT(INPUT_KEYBOARD, KEYBDINPUT(vk_code, 0, KEYEVENTF_KEYUP, 0, 0)),
            INPUT(
                INPUT_KEYBOARD,
                KEYBDINPUT(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0, 0),
            ),
        )
        ctypes.windll.user32.SendInput(
            len(inputs),
            ctypes.byref((INPUT * len(inputs))(*inputs)),
            ctypes.sizeof(INPUT),
        )

    def on_hotkey(self) -> None:
        # 用锁避免用户连续触发快捷键导致并发请求
        if not self.lock.acquire(blocking=False):
            return
        # 先展示浮窗并进入 loading，直到接口返回后替换为结果
        self.bridge.show_loading.emit()
        # 翻译请求放到后台线程，避免热键回调线程被网络请求阻塞
        threading.Thread(target=self.translate_selected_text, daemon=True).start()

    def run(self) -> None:
        hotkey = self.config["hotkey"]
        keyboard.add_hotkey(hotkey, self.on_hotkey)
        print(f"已启动。先用鼠标选中文本，再按 {hotkey} 自动识别中英并翻译。")
        try:
            self.qt_app.exec()
        finally:
            keyboard.unhook_all_hotkeys()


def main() -> None:
    cfg = load_config()
    app = TranslateHotkeyApp(cfg)
    app.run()


if __name__ == "__main__":
    main()
