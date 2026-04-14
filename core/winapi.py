from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

import keyboard
import pyperclip

# ── 虚拟键码 ──────────────────────────────────────────────────────────────────
VK_CONTROL = 0x11
VK_C       = 0x43
VK_INSERT  = 0x2D
VK_LBUTTON = 0x01
VK_ESCAPE  = 0x1B

INPUT_KEYBOARD  = 1
KEYEVENTF_KEYUP = 0x0002

# 32/64 位兼容的指针类型
ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong


# ── ctypes 输入结构体 ──────────────────────────────────────────────────────────

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk",         wintypes.WORD),
        ("wScan",       wintypes.WORD),
        ("dwFlags",     wintypes.DWORD),
        ("time",        wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("ki", KEYBDINPUT)]


# ── 鼠标 / 屏幕 ───────────────────────────────────────────────────────────────

def get_cursor_pos() -> tuple[int, int]:
    """返回当前鼠标坐标 (x, y)"""
    pt = wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def get_screen_size() -> tuple[int, int]:
    """返回主屏幕分辨率 (width, height)"""
    user32 = ctypes.windll.user32
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def is_key_down(vk_code: int) -> bool:
    """检测指定虚拟键当前是否处于按下状态"""
    return bool(ctypes.windll.user32.GetAsyncKeyState(vk_code) & 0x8000)


# ── 键盘输入模拟 ───────────────────────────────────────────────────────────────

def _send_ctrl_combo(vk_code: int) -> None:
    """通过 SendInput 模拟发送 Ctrl+<vk_code> 组合键"""
    inputs = (
        INPUT(INPUT_KEYBOARD, KEYBDINPUT(VK_CONTROL, 0, 0, 0, 0)),
        INPUT(INPUT_KEYBOARD, KEYBDINPUT(vk_code,   0, 0, 0, 0)),
        INPUT(INPUT_KEYBOARD, KEYBDINPUT(vk_code,   0, KEYEVENTF_KEYUP, 0, 0)),
        INPUT(INPUT_KEYBOARD, KEYBDINPUT(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0, 0)),
    )
    ctypes.windll.user32.SendInput(
        len(inputs),
        ctypes.byref((INPUT * len(inputs))(*inputs)),
        ctypes.sizeof(INPUT),
    )


# ── 复制触发策略（多种方式提升兼容性）────────────────────────────────────────────

def _trigger_by_keyboard()      -> None: keyboard.press_and_release("ctrl+c")
def _trigger_by_ctrl_insert()   -> None: keyboard.press_and_release("ctrl+insert")
def _trigger_by_winapi_c()      -> None: _send_ctrl_combo(VK_C)
def _trigger_by_winapi_insert() -> None: _send_ctrl_combo(VK_INSERT)


def _wait_clipboard_changed(sentinel: str, timeout: float) -> bool:
    """轮询剪贴板，直到内容不再是哨兵值或超时"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        current = (pyperclip.paste() or "").strip()
        if current and current != sentinel:
            return True
        time.sleep(0.03)
    return False


def capture_selected_text() -> str:
    """
    获取当前选中文本。

    通过哨兵值机制判断剪贴板是否发生了新的复制：
    依次尝试 4 种复制触发方式，循环两轮以兼容微信等响应较慢的应用。
    无论成功与否，最终都会恢复原始剪贴板内容。
    """
    original_clip = pyperclip.paste()
    sentinel = f"__translate_sentinel_{time.time_ns()}__"

    try:
        pyperclip.copy(sentinel)
        time.sleep(0.03)

        # 等待热键释放，微信等应用需要更多时间才能响应复制
        time.sleep(0.22)

        triggers = (
            _trigger_by_keyboard,
            _trigger_by_winapi_c,
            _trigger_by_ctrl_insert,
            _trigger_by_winapi_insert,
        )
        for _ in range(2):
            for trigger in triggers:
                trigger()
                if _wait_clipboard_changed(sentinel, timeout=1.0):
                    return (pyperclip.paste() or "").strip()
            time.sleep(0.06)

        return ""
    finally:
        pyperclip.copy(original_clip)
