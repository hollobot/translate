from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .config import save_config


# ─────────────────────────────────────────────────────────────────────────────
# 数字步进器（替代 QSpinBox 原生箭头按钮）
# ─────────────────────────────────────────────────────────────────────────────

class NumberStepper(QFrame):
    """带 − / + 按钮的数字步进控件，样式统一、交互清晰"""

    valueChanged = Signal(int)

    def __init__(
        self,
        min_val: int = 0,
        max_val: int = 100,
        value: int = 0,
        suffix: str = "",
        parent: QWidget = None,
    ):
        super().__init__(parent)
        self._min    = min_val
        self._max    = max_val
        self._value  = value
        self._suffix = suffix
        self._build()

    def _build(self) -> None:
        self.setFixedHeight(38)
        self.setObjectName("stepper")
        self.setStyleSheet(
            "QFrame#stepper {"
            "  background: rgba(255,255,255,0.92);"
            "  border: 1px solid rgba(148,163,184,0.5);"
            "  border-radius: 8px;"
            "}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._minus_btn = self._make_btn("−", left=True)
        self._minus_btn.clicked.connect(lambda: self.set_value(self._value - 1))

        # 数值显示区域，左右加分隔线
        self._display = QLabel(self._display_text())
        self._display.setAlignment(Qt.AlignCenter)
        self._display.setStyleSheet(
            "QLabel {"
            "  color: #0f172a; font-size: 13px; background: transparent;"
            "  border: none;"
            "  border-left:  1px solid rgba(148,163,184,0.4);"
            "  border-right: 1px solid rgba(148,163,184,0.4);"
            "}"
        )

        self._plus_btn = self._make_btn("+", left=False)
        self._plus_btn.clicked.connect(lambda: self.set_value(self._value + 1))

        layout.addWidget(self._minus_btn)
        layout.addWidget(self._display, 1)
        layout.addWidget(self._plus_btn)

        self._refresh_btn_state()

    def _make_btn(self, text: str, left: bool) -> QPushButton:
        """构造左侧或右侧的步进按钮"""
        btn = QPushButton(text)
        btn.setFixedWidth(36)
        btn.setCursor(Qt.PointingHandCursor)
        # 左侧按钮圆左角，右侧按钮圆右角
        radius = "border-radius: 7px 0 0 7px;" if left else "border-radius: 0 7px 7px 0;"
        btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: transparent; border: none; {radius}"
            f"  color: #64748b; font-size: 18px; font-weight: 400;"
            f"}}"
            f"QPushButton:hover   {{ background: rgba(59,130,246,0.1); color: #3b82f6; }}"
            f"QPushButton:pressed {{ background: rgba(59,130,246,0.2); }}"
            f"QPushButton:disabled {{ color: rgba(148,163,184,0.35); }}"
        )
        return btn

    def _display_text(self) -> str:
        return f"{self._value}{self._suffix}"

    def set_value(self, v: int) -> None:
        v = max(self._min, min(self._max, v))
        if v == self._value:
            return
        self._value = v
        self._display.setText(self._display_text())
        self._refresh_btn_state()
        self.valueChanged.emit(v)

    def value(self) -> int:
        return self._value

    def _refresh_btn_state(self) -> None:
        """到达边界时禁用对应按钮"""
        self._minus_btn.setEnabled(self._value > self._min)
        self._plus_btn.setEnabled(self._value < self._max)


# ─────────────────────────────────────────────────────────────────────────────
# 热键录制控件
# ─────────────────────────────────────────────────────────────────────────────

class HotkeyEdit(QLineEdit):
    """
    点击后进入录制模式，捕获组合键并转为 keyboard 库格式（如 ctrl+shift+t）。
    录制状态有明显的视觉高亮，与普通输入框状态区分。
    """

    # Qt 特殊键 → keyboard 库名称映射
    _SPECIAL_KEYS: dict[int, str] = {
        Qt.Key_Space: "space",       Qt.Key_Tab: "tab",
        Qt.Key_Return: "enter",      Qt.Key_Enter: "enter",
        Qt.Key_Backspace: "backspace", Qt.Key_Delete: "delete",
        Qt.Key_Insert: "insert",     Qt.Key_Home: "home",
        Qt.Key_End: "end",           Qt.Key_PageUp: "page up",
        Qt.Key_PageDown: "page down",
        Qt.Key_Left: "left",         Qt.Key_Right: "right",
        Qt.Key_Up: "up",             Qt.Key_Down: "down",
        Qt.Key_F1:  "f1",  Qt.Key_F2:  "f2",  Qt.Key_F3:  "f3",  Qt.Key_F4:  "f4",
        Qt.Key_F5:  "f5",  Qt.Key_F6:  "f6",  Qt.Key_F7:  "f7",  Qt.Key_F8:  "f8",
        Qt.Key_F9:  "f9",  Qt.Key_F10: "f10", Qt.Key_F11: "f11", Qt.Key_F12: "f12",
    }

    # 普通状态
    _NORMAL_SS = (
        "QLineEdit {"
        "  background: rgba(255,255,255,0.92);"
        "  border: 1px solid rgba(148,163,184,0.5);"
        "  border-radius: 8px; color: #0f172a; padding: 0 10px; font-size: 13px;"
        "}"
        "QLineEdit:hover { border-color: rgba(100,116,139,0.7); }"
    )

    # 录制中状态：加粗蓝色边框 + 蓝色背景底色，给用户明确的"正在录制"反馈
    _RECORDING_SS = (
        "QLineEdit {"
        "  background: rgba(219,234,254,0.75);"
        "  border: 2px solid #3b82f6;"
        "  border-radius: 8px; color: #1e40af;"
        "  padding: 0 10px; font-size: 13px; font-weight: 600;"
        "}"
    )

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setStyleSheet(self._NORMAL_SS)
        self.setPlaceholderText("点击此处，然后按下组合键…")
        self._recording = False

    def mousePressEvent(self, event) -> None:
        # 进入录制模式，切换为蓝色高亮样式
        self._recording = True
        self.setText("")
        self.setPlaceholderText("● 录制中 · 请按下组合键…")
        self.setStyleSheet(self._RECORDING_SS)
        self.setFocus()
        super().mousePressEvent(event)

    def focusOutEvent(self, event) -> None:
        # 失焦时退出录制模式，恢复普通样式
        if self._recording:
            self._recording = False
            self.setPlaceholderText("点击此处，然后按下组合键…")
            self.setStyleSheet(self._NORMAL_SS)
        super().focusOutEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if not self._recording:
            super().keyPressEvent(event)
            return

        key = event.key()
        # 单独按下修饰键不构成有效热键
        if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
            return

        parts = []
        mods = event.modifiers()
        if mods & Qt.ControlModifier: parts.append("ctrl")
        if mods & Qt.AltModifier:     parts.append("alt")
        if mods & Qt.ShiftModifier:   parts.append("shift")

        # 特殊键表查找，普通可打印字符直接转小写
        key_name = self._SPECIAL_KEYS.get(key)
        if key_name is None and 0x20 <= key <= 0x7E:
            key_name = chr(key).lower()

        if key_name:
            parts.append(key_name)
            hotkey_str = "+".join(parts)

            # keyboard 库用 '+' 做分隔符，若 key_name 本身是 '+' 会产生空组件导致崩溃，拒绝此类按键
            if any(p == "" for p in hotkey_str.split("+")):
                event.accept()
                return

            self.setText(hotkey_str)
            # 录制完成，恢复普通样式
            self._recording = False
            self.setPlaceholderText("点击此处，然后按下组合键…")
            self.setStyleSheet(self._NORMAL_SS)

        event.accept()


# ─────────────────────────────────────────────────────────────────────────────
# 设置窗口
# ─────────────────────────────────────────────────────────────────────────────

class SettingsWindow(QWidget):
    """无边框设置窗口，支持拖拽，配置 API 参数与全局热键"""

    # 保存成功后发出，携带新配置 dict
    saved = Signal(dict)

    _INPUT_STYLE = (
        "QLineEdit {"
        "  background: rgba(255,255,255,0.92);"
        "  border: 1px solid rgba(148,163,184,0.5);"
        "  border-radius: 8px; color: #0f172a; padding: 0 10px; font-size: 13px;"
        "}"
        "QLineEdit:focus {"
        "  border: 1.5px solid #3b82f6; background: rgba(239,246,255,0.96);"
        "}"
    )

    _INPUT_ERROR_STYLE = (
        "QLineEdit {"
        "  border: 1.5px solid rgba(239,68,68,0.75);"
        "  background: rgba(254,226,226,0.9);"
        "  border-radius: 8px; color: #0f172a; padding: 0 10px; font-size: 13px;"
        "}"
    )

    def __init__(self, config: dict, parent: QWidget = None):
        super().__init__(parent)
        self._drag_pos = None
        self._config   = config.copy()
        self._build_ui()
        self._load_values()

    # ── UI 构建 ──────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(500, 460)

        # 卡片容器（留边距给阴影）
        self.card = QFrame(self)
        self.card.setObjectName("settingsCard")
        self.card.setGeometry(14, 10, 472, 440)
        self.card.setStyleSheet(
            "QFrame#settingsCard {"
            "  background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "    stop:0 rgba(239,246,255,0.98), stop:1 rgba(255,255,255,0.99));"
            "  border: 1px solid rgba(147,197,253,0.85); border-radius: 18px;"
            "}"
        )

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(15, 23, 42, 85))
        self.card.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(30, 22, 30, 26)
        layout.setSpacing(0)

        layout.addLayout(self._build_title_bar())
        layout.addSpacing(22)

        # ── API 配置区 ──
        layout.addWidget(self._section_label("API 配置"))
        layout.addSpacing(12)

        self.appid_input = self._make_input("输入百度翻译 AppID")
        layout.addWidget(self._field_row("AppID", self.appid_input))
        layout.addSpacing(10)

        secret_widget, self.secret_input = self._build_secret_field()
        layout.addWidget(self._field_row("密钥", secret_widget))
        layout.addSpacing(10)

        # 超时使用自定义步进器
        self.timeout_stepper = NumberStepper(min_val=2, max_val=30, value=8, suffix=" 秒")
        layout.addWidget(self._field_row("超时", self.timeout_stepper))
        layout.addSpacing(22)

        # ── 快捷键区 ──
        layout.addWidget(self._section_label("快捷键"))
        layout.addSpacing(12)

        self.hotkey_edit = HotkeyEdit()
        self.hotkey_edit.setFixedHeight(38)
        layout.addWidget(self._field_row("翻译热键", self.hotkey_edit))

        layout.addStretch()
        layout.addLayout(self._build_buttons())

    def _build_title_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(8)

        icon_lbl = QLabel("T")
        icon_lbl.setFixedSize(32, 32)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #3b82f6,stop:1 #2563eb);"
            "border-radius: 8px; color: white; font-size: 15px; font-weight: 700;"
        )

        title = QLabel("Smart Translate 设置")
        title.setStyleSheet(
            "color: #0f172a; font-size: 15px; font-weight: 700; letter-spacing: 0.3px;"
        )

        close_btn = QPushButton("×")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton { background: rgba(148,163,184,0.15); border: none;"
            "  border-radius: 14px; color: #64748b; font-size: 17px; font-weight: 700; }"
            "QPushButton:hover { background: rgba(239,68,68,0.15); color: #ef4444; }"
        )
        close_btn.clicked.connect(self.hide)

        bar.addWidget(icon_lbl)
        bar.addWidget(title)
        bar.addStretch()
        bar.addWidget(close_btn)
        return bar

    def _build_secret_field(self) -> tuple[QWidget, QLineEdit]:
        """密钥输入框 + 显示/隐藏切换按钮"""
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        inp = self._make_input("输入百度翻译密钥")
        inp.setEchoMode(QLineEdit.Password)

        toggle = QPushButton("显示")
        toggle.setFixedSize(48, 38)
        toggle.setCursor(Qt.PointingHandCursor)
        toggle.setCheckable(True)
        toggle.setStyleSheet(
            "QPushButton { background: rgba(148,163,184,0.15);"
            "  border: 1px solid rgba(148,163,184,0.4); border-radius: 8px;"
            "  color: #64748b; font-size: 11px; font-weight: 600; }"
            "QPushButton:checked { background: rgba(59,130,246,0.12); color: #3b82f6; }"
            "QPushButton:hover { background: rgba(148,163,184,0.28); }"
        )

        def _on_toggle(checked: bool) -> None:
            inp.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
            toggle.setText("隐藏" if checked else "显示")

        toggle.toggled.connect(_on_toggle)
        row.addWidget(inp)
        row.addWidget(toggle)
        return container, inp

    def _build_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedSize(90, 36)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(
            "QPushButton { background: rgba(148,163,184,0.18);"
            "  border: 1px solid rgba(148,163,184,0.35); border-radius: 10px;"
            "  color: #475569; font-size: 13px; font-weight: 600; }"
            "QPushButton:hover { background: rgba(148,163,184,0.32); }"
        )
        cancel_btn.clicked.connect(self.hide)

        save_btn = QPushButton("保存")
        save_btn.setFixedSize(90, 36)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "    stop:0 #3b82f6,stop:1 #2563eb);"
            "  border: none; border-radius: 10px; color: white; font-size: 13px; font-weight: 600; }"
            "QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "    stop:0 #60a5fa,stop:1 #3b82f6); }"
            "QPushButton:pressed { background: #1d4ed8; }"
        )
        save_btn.clicked.connect(self._on_save)

        row.addWidget(cancel_btn)
        row.addWidget(save_btn)
        return row

    # ── 辅助方法 ──────────────────────────────────────────────────────────────

    def _make_input(self, placeholder: str) -> QLineEdit:
        inp = QLineEdit()
        inp.setFixedHeight(38)
        inp.setPlaceholderText(placeholder)
        inp.setStyleSheet(self._INPUT_STYLE)
        # 开始输入时自动清除错误高亮
        inp.textChanged.connect(lambda _: inp.setStyleSheet(self._INPUT_STYLE))
        return inp

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "color: #3b82f6; font-size: 11px; font-weight: 700; letter-spacing: 0.9px;"
        )
        return lbl

    def _field_row(self, label_text: str, widget: QWidget) -> QWidget:
        """标签（右对齐固定宽度）+ 控件，横向排列"""
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(14)

        lbl = QLabel(label_text)
        lbl.setFixedWidth(62)
        lbl.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
        lbl.setStyleSheet("color: #475569; font-size: 13px; font-weight: 600;")

        row.addWidget(lbl)
        row.addWidget(widget)
        return container

    # ── 数据操作 ──────────────────────────────────────────────────────────────

    def _load_values(self) -> None:
        """将配置回填到表单"""
        self.appid_input.setText(self._config.get("appid", ""))
        self.secret_input.setText(self._config.get("secret", ""))
        self.timeout_stepper.set_value(int(self._config.get("timeout", 8)))
        self.hotkey_edit.setText(self._config.get("hotkey", "ctrl+shift+t"))

    def _on_save(self) -> None:
        appid  = self.appid_input.text().strip()
        secret = self.secret_input.text().strip()
        hotkey = self.hotkey_edit.text().strip()

        # 校验必填项，高亮错误字段后中止
        has_error = False
        if not appid:
            self.appid_input.setStyleSheet(self._INPUT_ERROR_STYLE)
            has_error = True
        if not secret:
            self.secret_input.setStyleSheet(self._INPUT_ERROR_STYLE)
            has_error = True
        if not hotkey or has_error:
            return

        new_cfg = {
            "appid":   appid,
            "secret":  secret,
            "timeout": self.timeout_stepper.value(),
            "hotkey":  hotkey,
        }
        save_config(new_cfg)
        self.saved.emit(new_cfg)
        self.hide()

    # ── 拖拽移动 ──────────────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() & Qt.LeftButton and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
