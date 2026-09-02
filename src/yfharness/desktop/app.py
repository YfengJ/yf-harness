"""Native Qt Quick desktop entry point."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def main() -> None:
    try:
        from PySide6.QtCore import QPointF, QTimer, QUrl
        from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication, QIcon
        from PySide6.QtQml import QQmlApplicationEngine
        from PySide6.QtQuick import QQuickItem, QQuickWindow
    except ImportError as exc:
        raise SystemExit("桌面组件未安装。请运行：pip install 'yf-harness[desktop]'") from exc

    from yfharness.desktop.controller import DesktopController

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--screenshot")
    parser.add_argument("--preview-tab", type=int, choices=range(3))
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument("--stress-preview", action="store_true")
    parser.add_argument("--empty-preview", action="store_true")
    parser.add_argument("--preview-command", action="store_true")
    parser.add_argument("--layout-report")
    args, qt_args = parser.parse_known_args()
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    application = QGuiApplication([sys.argv[0], *qt_args])
    application.setApplicationName("YF-Harness")
    application.setApplicationDisplayName("YF-Harness")
    application.setOrganizationName("YF-Harness")
    application.setOrganizationDomain("local.yfharness")
    available_fonts = set(QFontDatabase.families())
    for family in ("Avenir Next", "Segoe UI Variable", "Noto Sans CJK SC", "Noto Sans"):
        if family in available_fonts:
            application.setFont(QFont(family))
            break

    root = Path(__file__).resolve().parent
    application.setWindowIcon(QIcon(str(root / "assets" / "app-icon.png")))
    controller = DesktopController()
    if args.screenshot:
        controller.seedPreview(stress=args.stress_preview)
        if args.empty_preview:
            controller.newSession()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("controller", controller)
    engine.load(QUrl.fromLocalFile(str(root / "qml" / "Main.qml")))
    if not engine.rootObjects():
        raise SystemExit("无法加载桌面界面资源")
    window = engine.rootObjects()[0]
    if args.width:
        window.setProperty("width", max(1040, args.width))
    if args.height:
        window.setProperty("height", max(720, args.height))
    if args.screenshot:
        if args.preview_tab is not None:
            window.setProperty("inspectorTab", args.preview_tab)
            window.setProperty("inspectorOpen", True)
        window.setProperty("commandPreviewRequested", args.preview_command)
    application.aboutToQuit.connect(controller.shutdown)

    if args.screenshot:

        def capture() -> None:
            if not isinstance(window, QQuickWindow):
                raise RuntimeError("桌面根窗口类型无效")
            image = window.grabWindow()
            if not image.save(args.screenshot):
                raise RuntimeError(f"无法保存截图：{args.screenshot}")
            if args.layout_report:
                items: dict[str, object] = {}
                layout: dict[str, object] = {
                    "window": {"width": window.width(), "height": window.height()},
                    "items": items,
                }
                for name in (
                    "sidebar",
                    "workspace",
                    "composer",
                    "promptInput",
                    "taskStatusBar",
                    "composerActions",
                    "sessionTitle",
                    "sidebarSettings",
                    "attachmentButton",
                    "sendButton",
                ):
                    pending = [window.contentItem()]
                    item: QQuickItem | None = None
                    while pending:
                        candidate = pending.pop()
                        if candidate.objectName() == name:
                            item = candidate
                            break
                        pending.extend(candidate.childItems())
                    if item is None:
                        continue
                    origin = item.mapToScene(QPointF(0, 0))
                    width = float(item.property("width"))
                    height = float(item.property("height"))
                    items[name] = {
                        "x": origin.x(),
                        "y": origin.y(),
                        "width": width,
                        "height": height,
                        "within_window": (
                            origin.x() >= -0.5
                            and origin.y() >= -0.5
                            and origin.x() + width <= window.width() + 0.5
                            and origin.y() + height <= window.height() + 0.5
                        ),
                    }
                Path(args.layout_report).write_text(
                    json.dumps(layout, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            application.quit()

        QTimer.singleShot(1200, capture)
    elif args.smoke_test:
        QTimer.singleShot(300, application.quit)
    else:
        QTimer.singleShot(0, controller.bootstrap)
    raise SystemExit(application.exec())


if __name__ == "__main__":
    main()
