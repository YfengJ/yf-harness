[app]
title = YF-Harness
project_dir = ../../src/yfharness/desktop
input_file = ../../src/yfharness/desktop/app.py
exec_directory = dist
project_file =
icon = build/desktop/AppIcon.icns

[python]
python_path = .venv/bin/python3
packages = Nuitka==4.1.3,ordered-set==4.1.0,zstandard==0.25.0
android_packages = buildozer==1.5.0,cython==0.29.33

[qt]
qml_files = qml/Main.qml
excluded_qml_plugins = QtCharts,QtQuick3D,QtSensors,QtTest,QtWebEngine
modules = Core,Gui,Network,OpenGL,Qml,QmlMeta,QmlModels,QmlWorkerScript,Quick,QuickControls2,QuickTemplates2
plugins = imageformats,networkaccess,networkinformation,platforms,platforms/darwin,platformthemes,tls

[android]
wheel_pyside =
wheel_shiboken =
plugins =

[nuitka]
macos.permissions =
mode = standalone
extra_args = --quiet --noinclude-qt-translations --include-package=yfharness --include-package-data=yfharness.desktop --macos-app-version=0.4.0 --macos-app-name=YF-Harness --macos-app-mode=gui

[buildozer]
mode = debug
recipe_dir =
jars_dir =
ndk_path =
sdk_path =
local_libs =
arch =
