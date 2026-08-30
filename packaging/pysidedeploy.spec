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
excluded_qml_plugins = Qt3D,QtCharts,QtDataVisualization,QtGraphs,QtLocation,QtMultimedia,QtPdf,QtPositioning,QtQuick3D,QtRemoteObjects,QtScxml,QtSensors,QtTest,QtTextToSpeech,QtWebChannel,QtWebEngine,QtWebSockets,QtWebView
modules = Core,Gui,Network,OpenGL,Qml,QmlMeta,QmlModels,QmlWorkerScript,Quick,QuickControls2,QuickTemplates2
plugins = imageformats,networkaccess,networkinformation,platforms,platforms/darwin,platformthemes,tls

[android]
wheel_pyside =
wheel_shiboken =
plugins =

[nuitka]
macos.permissions =
mode = standalone
extra_args = --quiet --disable-cache=ccache --noinclude-qt-translations --include-package=yfharness --include-package-data=yfharness.desktop --macos-app-version=0.8.0 --macos-app-name=YF-Harness --macos-app-mode=gui --noinclude-dlls=Qt3D* --noinclude-dlls=QtCharts* --noinclude-dlls=QtDataVisualization* --noinclude-dlls=QtGraphs* --noinclude-dlls=QtLocation* --noinclude-dlls=QtMultimedia* --noinclude-dlls=QtPdf* --noinclude-dlls=QtPositioning* --noinclude-dlls=QtQuick3D* --noinclude-dlls=QtRemoteObjects* --noinclude-dlls=QtScxml* --noinclude-dlls=QtSensors* --noinclude-dlls=QtTest* --noinclude-dlls=QtTextToSpeech* --noinclude-dlls=QtWebChannel* --noinclude-dlls=QtWebEngine* --noinclude-dlls=QtWebSockets* --noinclude-dlls=QtWebView*

[buildozer]
mode = debug
recipe_dir =
jars_dir =
ndk_path =
sdk_path =
local_libs =
arch =
