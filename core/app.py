from __future__ import annotations

import threading

import keyboard
from PySide6.QtCore import QObject, QPoint, QTimer, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .popup import TranslatePopup
from .settings import SettingsWindow
from .translator import baidu_translate, detect_lang_direction
from .winapi import (
    VK_ESCAPE,
    VK_LBUTTON,
    capture_selected_text,
    get_cursor_pos,
    get_screen_size,
    is_key_down,
)


class UiBridge(QObject):
    """跨线程 UI 通信桥：后台翻译线程通过 Signal 安全更新主线程 UI"""
    update_result = Signal(str, str, bool)
    show_loading  = Signal()


class TranslateHotkeyApp:
    """主控制器：管理热键、翻译线程、弹窗显示与系统托盘"""

    def __init__(self, config: dict) -> None:
        self.config = config
        self.lock   = threading.Lock()

        self.qt_app = QApplication([])
        self.popup  = TranslatePopup()

        self.bridge = UiBridge()
        self.bridge.update_result.connect(self._show_result)
        self.bridge.show_loading.connect(self._show_loading)

        # 轮询鼠标与 ESC 状态，实现点击外部或按 ESC 关闭弹窗
        self._state_timer    = QTimer()
        self._state_timer.setInterval(35)
        self._state_timer.timeout.connect(self._check_popup_state)
        self._prev_left_down = False
        self._prev_esc_down  = False

        # 设置窗口延迟创建（首次打开时初始化）
        self._settings_win: SettingsWindow | None = None

        self._setup_tray()

    # ── 系统托盘 ──────────────────────────────────────────────────────────────

    def _setup_tray(self) -> None:
        """初始化托盘图标与右键菜单"""
        self.tray = QSystemTrayIcon(self._make_tray_icon(), self.qt_app)
        self.tray.setToolTip("Smart Translate — 运行中")

        menu = QMenu()
        menu.setStyleSheet(
            "QMenu { background: white; border: 1px solid rgba(148,163,184,0.4);"
            "  border-radius: 10px; padding: 4px; }"
            "QMenu::item { padding: 7px 18px; color: #0f172a; font-size: 13px; border-radius: 6px; }"
            "QMenu::item:selected { background: rgba(59,130,246,0.1); color: #1d4ed8; }"
            "QMenu::separator { height: 1px; background: rgba(148,163,184,0.3); margin: 3px 8px; }"
        )
        menu.addAction("⚙  设置").triggered.connect(self.open_settings)
        menu.addSeparator()
        menu.addAction("✕  退出").triggered.connect(self.qt_app.quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _make_tray_icon(self) -> QIcon:
        """绘制蓝色圆形托盘图标（内含白色 T 字），无需外部图片文件"""
        px = QPixmap(32, 32)
        px.fill(Qt.transparent)
        painter = QPainter(px)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(QColor("#3b82f6")))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, 32, 32)
        painter.setPen(QPen(QColor("white")))
        painter.setFont(QFont("Microsoft YaHei UI", 14, QFont.Bold))
        painter.drawText(px.rect(), Qt.AlignCenter, "T")
        painter.end()
        return QIcon(px)

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.DoubleClick:
            self.open_settings()

    # ── 设置窗口 ──────────────────────────────────────────────────────────────

    def open_settings(self) -> None:
        """打开设置窗口，居中显示"""
        if self._settings_win is None:
            self._settings_win = SettingsWindow(self.config)
            self._settings_win.saved.connect(self._on_settings_saved)
        else:
            # 刷新表单为当前配置
            self._settings_win._config = self.config.copy()
            self._settings_win._load_values()

        screen = self.qt_app.primaryScreen().geometry()
        w, h = self._settings_win.width(), self._settings_win.height()
        self._settings_win.move((screen.width() - w) // 2, (screen.height() - h) // 2)
        self._settings_win.show()
        self._settings_win.raise_()

    def _on_settings_saved(self, new_cfg: dict) -> None:
        """
        配置保存后同步内存配置。
        若热键有变更，先清除所有钩子再重新注册，避免 keyboard 库内部状态冲突。
        """
        old_hotkey = self.config.get("hotkey", "")
        new_hotkey = new_cfg.get("hotkey", "")
        self.config = new_cfg

        if old_hotkey != new_hotkey:
            keyboard.unhook_all_hotkeys()
            keyboard.add_hotkey(new_hotkey, self._on_hotkey)
            print(f"热键已更新: {old_hotkey} → {new_hotkey}")

    # ── 翻译流程 ──────────────────────────────────────────────────────────────

    def _on_hotkey(self) -> None:
        # 用锁避免连续触发热键导致并发请求
        if not self.lock.acquire(blocking=False):
            return
        self.bridge.show_loading.emit()
        # 翻译放到后台线程，不阻塞热键回调
        threading.Thread(target=self._translate, daemon=True).start()

    def _translate(self) -> None:
        try:
            text = capture_selected_text()
            if not text:
                self.bridge.update_result.emit("未检测到选中文本", "复制失败", True)
                return

            from_lang, to_lang = detect_lang_direction(text)
            result = baidu_translate(
                text,
                self.config["appid"],
                self.config["secret"],
                from_lang,
                to_lang,
                int(self.config.get("timeout", 8)),
            )
            self.bridge.update_result.emit(result, f"{from_lang} → {to_lang}", False)
        except Exception as e:
            self.bridge.update_result.emit(f"翻译失败: {e}", "接口异常", True)
        finally:
            self.lock.release()

    # ── 弹窗管理 ──────────────────────────────────────────────────────────────

    def _show_result(self, text: str, lang_pair: str, is_error: bool) -> None:
        self.popup.set_content(text, lang_pair, is_error)
        self._show_popup(bring_front=True)

    def _show_loading(self) -> None:
        self.popup.show_shell()
        self._show_popup(bring_front=False)
        # 先显示弹窗壳，稍后启动 loading 动画
        QTimer.singleShot(90, self.popup.start_loading)

    def _show_popup(self, bring_front: bool) -> None:
        self.popup.adjustSize()
        x, y   = get_cursor_pos()
        sw, sh = get_screen_size()

        # 跟随鼠标，同时限制在屏幕内
        px = min(max(10, x + 12), max(10, sw - self.popup.width()  - 10))
        py = min(max(10, y + 14), max(10, sh - self.popup.height() - 10))

        self.popup.move(px, py)
        self.popup.show()
        if not self._state_timer.isActive():
            self._state_timer.start()
        if bring_front:
            self.popup.raise_()

    def _check_popup_state(self) -> None:
        """每 35ms 轮询一次，处理点击外部和 ESC 关闭弹窗"""
        if not self.popup.isVisible():
            return

        left_down = is_key_down(VK_LBUTTON)
        esc_down  = is_key_down(VK_ESCAPE)

        if esc_down and not self._prev_esc_down:
            self.popup.hide()

        if left_down and not self._prev_left_down:
            mx, my = get_cursor_pos()
            if not self.popup.geometry().contains(QPoint(mx, my)):
                self.popup.hide()

        self._prev_left_down = left_down
        self._prev_esc_down  = esc_down

    # ── 启动 ─────────────────────────────────────────────────────────────────

    def run(self) -> None:
        hotkey = self.config["hotkey"]
        keyboard.add_hotkey(hotkey, self._on_hotkey)

        # 首次运行（appid/secret 为空）自动弹出设置窗口引导配置
        if not self.config.get("appid") or not self.config.get("secret"):
            QTimer.singleShot(400, self.open_settings)
        else:
            print(f"已启动。先用鼠标选中文本，再按 {hotkey} 自动识别中英并翻译。")
            print("右键任务栏托盘图标可打开设置或退出。")
        try:
            self.qt_app.exec()
        finally:
            keyboard.unhook_all_hotkeys()
