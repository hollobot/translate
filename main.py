from __future__ import annotations

from core.app import TranslateHotkeyApp
from core.config import load_config


def main() -> None:
    cfg = load_config()
    app = TranslateHotkeyApp(cfg)
    app.run()


if __name__ == "__main__":
    main()
