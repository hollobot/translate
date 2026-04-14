"""
SmartTranslate 打包脚本
将项目打包为单个 Windows exe 文件，图标与托盘图标保持一致。

构建前安装打包依赖（仅构建时需要，不影响运行时）：
    pip install pyinstaller pillow

运行：
    python build.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent


def generate_icon() -> Path:
    """
    使用 PySide6 绘制与托盘相同的蓝色圆形 T 字图标，
    再通过 Pillow 转换为包含多尺寸的标准 ICO 文件。
    """
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPixmap
    from PySide6.QtWidgets import QApplication

    # QPixmap 需要 QApplication 存在
    _app = QApplication.instance() or QApplication([])

    size = 256
    px = QPixmap(size, size)
    px.fill(Qt.transparent)

    painter = QPainter(px)
    painter.setRenderHint(QPainter.Antialiasing)
    # 蓝色圆形背景（内缩 8px 留出抗锯齿边距）
    painter.setBrush(QBrush(QColor("#3b82f6")))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(8, 8, size - 16, size - 16)
    # 白色 T 字居中
    painter.setPen(QPen(QColor("white")))
    painter.setFont(QFont("Microsoft YaHei UI", 130, QFont.Bold))
    painter.drawText(px.rect(), Qt.AlignCenter, "T")
    painter.end()

    # 先输出 PNG，再用 Pillow 生成多尺寸 ICO
    packaging_dir = ROOT / "packaging"
    packaging_dir.mkdir(exist_ok=True)

    png_path = packaging_dir / "_icon_tmp.png"
    px.save(str(png_path))

    from PIL import Image

    ico_path = packaging_dir / "icon.ico"
    with Image.open(str(png_path)) as img:
        img.save(
            str(ico_path),
            format="ICO",
            sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
        )
    png_path.unlink(missing_ok=True)

    print(f"  [✓] 图标已生成: {ico_path.name}")
    return ico_path


def run_pyinstaller(icon_path: Path) -> None:
    """调用 PyInstaller 将项目打包为单文件 exe"""
    packaging_dir = ROOT / "packaging"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",                          # 打包为单个 exe
        "--windowed",                         # 不弹出控制台窗口
        f"--icon={icon_path}",                # exe 图标
        "--name=SmartTranslate",              # 输出文件名
        "--clean",                            # 清理上次构建缓存
        f"--specpath={packaging_dir}",        # .spec 文件输出到 packaging/
        f"--workpath={packaging_dir / 'build'}",  # 编译临时文件输出到 packaging/build/
        # keyboard 库通过底层 hook 运行，需显式声明
        "--hidden-import=keyboard",
        "main.py",
    ]
    print(f"  [→] {' '.join(cmd[2:])}\n")
    subprocess.run(cmd, cwd=str(ROOT), check=True)


def main() -> None:
    print("=" * 52)
    print("   SmartTranslate  打包工具")
    print("=" * 52)

    print("\n[1/2] 生成图标")
    icon_path = generate_icon()

    print("\n[2/2] PyInstaller 打包")
    run_pyinstaller(icon_path)

    exe_path = ROOT / "dist" / "SmartTranslate.exe"
    print(f"\n{'=' * 52}")
    print(f"  打包完成 → {exe_path}")
    print(f"{'=' * 52}")
    print("\n注意：")
    print("  · config.json 自动生成在 exe 同级目录，首次运行会弹出设置窗口")
    print("  · 若热键注册失败，请以管理员身份运行 exe")


if __name__ == "__main__":
    main()
