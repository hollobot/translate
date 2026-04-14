from __future__ import annotations

from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtGui import QColor, QFont, QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QLabel,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class TranslatePopup(QWidget):
    """翻译结果悬浮弹窗，无边框、不抢焦点、跟随鼠标显示"""

    def __init__(self) -> None:
        super().__init__(None)
        self.min_width  = 420
        self.max_width  = 720
        self.min_height = 130
        self.max_height = 520
        self.loading_step = 0

        # Tool 标志使弹窗不抢占焦点，确保复制操作不受干扰
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
            "background: rgba(148,163,184,0.14); border-radius: 10px; padding: 2px 8px;"
        )

        # 只读 QTextEdit 仍支持鼠标选中与 Ctrl+C 复制
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_edit.setStyleSheet(
            "QTextEdit {"
            "  background: rgba(255,255,255,0.86);"
            "  border: 1px solid rgba(148,163,184,0.22);"
            "  border-radius: 10px; color: #0f172a; padding: 10px 12px;"
            "  selection-background-color: #bfdbfe;"
            "}"
            "QScrollBar:vertical { background: transparent; width: 10px; margin: 8px 2px; }"
            "QScrollBar::handle:vertical {"
            "  background: rgba(100,116,139,0.45); min-height: 30px; border-radius: 5px;"
            "}"
            "QScrollBar::handle:vertical:hover { background: rgba(59,130,246,0.62); }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }"
        )
        self.text_edit.setFont(QFont("Microsoft YaHei UI", 11))
        self.text_edit.installEventFilter(self)

        layout = QVBoxLayout()
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(8)
        layout.addWidget(self.title_label)
        layout.addWidget(self.meta_label, alignment=Qt.AlignLeft)
        layout.addWidget(self.text_edit)
        self.container.setLayout(layout)

        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.container)
        self.setLayout(root)

        self.loading_timer = QTimer(self)
        self.loading_timer.setInterval(260)
        self.loading_timer.timeout.connect(self._tick_loading)

    # ── 公开接口 ──────────────────────────────────────────────────────────────

    def show_shell(self) -> None:
        """先展示空壳弹窗，后续再切换为 loading 动画，提升感知响应速度"""
        self._stop_loading()
        self._set_error_style(False)
        self.meta_label.setText("ready")
        self.text_edit.setPlainText("\n")
        self._fit_size("正在准备翻译")

    def start_loading(self) -> None:
        self.loading_step = 0
        self.meta_label.setText("processing")
        self._set_error_style(False)
        text = "正在检测并翻译选中文本"
        self.text_edit.setPlainText(text)
        self._fit_size(text)
        self.loading_timer.start()

    def set_content(self, text: str, lang_pair: str, is_error: bool = False) -> None:
        """显示翻译结果或错误信息"""
        self._stop_loading()
        self._set_error_style(is_error)
        self.meta_label.setText(lang_pair or "")
        self.text_edit.setPlainText(text)
        self._fit_size(text)

    # ── 私有方法 ──────────────────────────────────────────────────────────────

    def _stop_loading(self) -> None:
        self.loading_timer.stop()

    def _tick_loading(self) -> None:
        self.loading_step = (self.loading_step + 1) % 4
        self.text_edit.setPlainText(f"正在检测并翻译选中文本{'.' * self.loading_step}")

    def _set_error_style(self, is_error: bool) -> None:
        if is_error:
            border, title, chip = "rgba(252,165,165,0.9)", "#7f1d1d", "rgba(248,113,113,0.2)"
            bg = "qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 rgba(255,241,242,0.98),stop:1 rgba(255,255,255,0.98))"
        else:
            border, title, chip = "rgba(147,197,253,0.9)", "#0f172a", "rgba(59,130,246,0.16)"
            bg = "qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 rgba(239,246,255,0.97),stop:1 rgba(255,255,255,0.98))"

        self.container.setStyleSheet(
            f"QFrame#card {{ background: {bg}; border: 1px solid {border}; border-radius: 16px; }}"
        )
        self.title_label.setStyleSheet(
            f"color: {title}; font-size: 13px; font-weight: 700; letter-spacing: 0.4px;"
        )
        self.meta_label.setStyleSheet(
            f"color: #475569; font-size: 11px; font-weight: 600;"
            f"background: {chip}; border-radius: 10px; padding: 2px 8px;"
        )

    def _fit_size(self, text: str) -> None:
        """根据文本内容动态调整弹窗尺寸"""
        target_w = min(self.max_width, max(self.min_width, 360 + len(text) * 3))
        self.text_edit.document().setTextWidth(target_w - 40)
        doc_h = int(self.text_edit.document().size().height()) + 14
        target_h = min(
            self.max_height,
            max(self.min_height, doc_h + self.meta_label.sizeHint().height() + 64),
        )
        self.resize(target_w, target_h)

    # ── 事件处理 ──────────────────────────────────────────────────────────────

    def eventFilter(self, watched, event) -> bool:
        if watched is self.text_edit and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Escape:
                self.hide()
                return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)
