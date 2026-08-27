"""Native Qt Quick desktop entry point."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main() -> None:
    try:
        from PySide6.QtCore import QTimer, QUrl
        from PySide6.QtGui import QGuiApplication, QIcon
        from PySide6.QtQml import QQmlApplicationEngine
        from PySide6.QtQuick import QQuickWindow
    except ImportError as exc:
        raise SystemExit("桌面组件未安装。请运行：pip install 'yf-harness[desktop]'") from exc

    from yfharness.desktop.controller import DesktopController

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--screenshot")
    parser.add_argument("--preview-tab", type=int, choices=range(3), default=0)
    args, qt_args = parser.parse_known_args()
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    application = QGuiApplication([sys.argv[0], *qt_args])
    application.setApplicationName("YF-Harness")
    application.setApplicationDisplayName("YF-Harness")
    application.setOrganizationName("YF-Harness")
    application.setOrganizationDomain("local.yfharness")

    root = Path(__file__).resolve().parent
    application.setWindowIcon(QIcon(str(root / "assets" / "app-icon.png")))
    controller = DesktopController()
    if args.screenshot:
        controller.seedPreview()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("controller", controller)
    engine.load(QUrl.fromLocalFile(str(root / "qml" / "Main.qml")))
    if not engine.rootObjects():
        raise SystemExit("无法加载桌面界面资源")
    if args.screenshot:
        engine.rootObjects()[0].setProperty("inspectorTab", args.preview_tab)
    application.aboutToQuit.connect(controller.shutdown)

    if args.screenshot:

        def capture() -> None:
            window = engine.rootObjects()[0]
            if not isinstance(window, QQuickWindow):
                raise RuntimeError("桌面根窗口类型无效")
            image = window.grabWindow()
            if not image.save(args.screenshot):
                raise RuntimeError(f"无法保存截图：{args.screenshot}")
            application.quit()

        QTimer.singleShot(1200, capture)
    elif args.smoke_test:
        QTimer.singleShot(300, application.quit)
    else:
        QTimer.singleShot(0, controller.bootstrap)
    raise SystemExit(application.exec())


if __name__ == "__main__":
    main()
