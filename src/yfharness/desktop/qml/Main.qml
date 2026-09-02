import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

ApplicationWindow {
    id: root
    width: 1440
    height: 900
    minimumWidth: 1040
    minimumHeight: 720
    visible: true
    title: (controller ? controller.currentSessionTitle : "YF-Harness") + " — YF-Harness"
    color: "#F4F1E8"

    readonly property color canvas: "#F4F1E8"
    readonly property color surface: "#FFFFFF"
    readonly property color surfaceSoft: "#ECEFF3"
    readonly property color raised: "#E3E8EE"
    readonly property color line: "#D4DAE2"
    readonly property color lineStrong: "#B8C1CD"
    readonly property color textPrimary: "#10223D"
    readonly property color textSecondary: "#48586B"
    readonly property color textMuted: "#768396"
    readonly property color accent: "#2E63D3"
    readonly property color accentHover: "#2557BE"
    readonly property color accentSoft: "#E1EAFF"
    readonly property color success: "#24866A"
    readonly property color successSoft: "#DDF3EB"
    readonly property color danger: "#B84A4A"
    readonly property color nav: "#10223D"
    readonly property color navSoft: "#183253"
    readonly property color navText: "#F8F6EF"
    readonly property color navMuted: "#9EADC0"
    property string approvalId: ""
    property int inspectorTab: 0
    property bool inspectorOpen: false
    property bool commandOpen: false
    property bool commandPreviewRequested: false
    property bool connectionsPreviewRequested: false
    property bool skillsPreviewRequested: false
    property bool githubPreviewRequested: false
    property string githubPendingSync: ""
    onCommandPreviewRequestedChanged: {
        if (commandPreviewRequested)
            Qt.callLater(function() { commandCenter.open() })
    }
    onConnectionsPreviewRequestedChanged: {
        if (connectionsPreviewRequested)
            Qt.callLater(function() { connectionsDialog.open() })
    }
    onSkillsPreviewRequestedChanged: {
        if (skillsPreviewRequested) {
            controller.filterSkills("$")
            Qt.callLater(function() { skillsDialog.open() })
        }
    }
    onGithubPreviewRequestedChanged: {
        if (githubPreviewRequested) {
            controller.refreshGitHub()
            Qt.callLater(function() { githubDialog.open() })
        }
    }

    function selectValue(combo, value) {
        var index = combo.find(value)
        combo.currentIndex = index >= 0 ? index : 0
    }

    function sendCurrentPrompt() {
        var value = promptInput.text.trim()
        if (!value)
            return
        controller.sendMessage(value, providerSelect.currentText, modelSelect.currentText,
                               workflowSelect.currentText, modeSelect.currentText,
                               permissionSelect.currentText)
        promptInput.clear()
    }

    function openInspector(tab) {
        root.inspectorTab = tab
        root.inspectorOpen = true
    }

    function runCommand(actionId) {
        commandCenter.close()
        if (actionId === "new") {
            controller.newSession()
            Qt.callLater(function() { promptInput.forceActiveFocus() })
        } else if (actionId === "plan") {
            root.selectValue(workflowSelect, "plan")
            root.selectValue(modeSelect, "plan")
            root.selectValue(permissionSelect, "deny_writes")
            Qt.callLater(function() { promptInput.forceActiveFocus() })
        } else if (actionId === "changes") {
            root.openInspector(2)
        } else if (actionId === "context") {
            root.openInspector(1)
        } else if (actionId === "usage") {
            root.openInspector(0)
            controller.refreshUsage()
        } else if (actionId === "skills") {
            controller.filterSkills("$")
            Qt.callLater(function() { skillsDialog.open() })
        } else if (actionId === "connections") {
            Qt.callLater(function() { connectionsDialog.open() })
        } else if (actionId === "github") {
            controller.refreshGitHub()
            Qt.callLater(function() { githubDialog.open() })
        } else if (actionId === "goal") {
            Qt.callLater(function() { goalPopup.open() })
        } else if (actionId === "project") {
            Qt.callLater(function() { projectFolderDialog.open() })
        }
    }

    function selectFirstMatchingCommand() {
        for (var i = 0; i < commandList.count; i++) {
            var item = commandList.itemAtIndex(i)
            if (item && item.queryMatch) {
                commandList.currentIndex = i
                return
            }
        }
        commandList.currentIndex = -1
    }

    function moveCommandSelection(direction) {
        if (commandList.count === 0)
            return
        var index = commandList.currentIndex
        for (var step = 0; step < commandList.count; step++) {
            index = (index + direction + commandList.count) % commandList.count
            var item = commandList.itemAtIndex(index)
            if (item && item.queryMatch) {
                commandList.currentIndex = index
                return
            }
        }
    }

    component Hairline: Rectangle {
        color: root.line
        implicitHeight: 1
        implicitWidth: 1
    }

    component QuietButton: Rectangle {
        id: quietButton
        property string label: ""
        property string glyph: ""
        property bool prominent: false
        property bool onDark: false
        signal clicked()
        implicitWidth: buttonContent.implicitWidth + 28
        implicitHeight: 36
        radius: 7
        color: prominent ? (buttonMouse.containsMouse ? root.accentHover : root.accent)
                         : (buttonMouse.containsMouse
                            ? (onDark ? root.navSoft : root.surfaceSoft) : "transparent")
        border.width: activeFocus ? 2 : (prominent ? 0 : 1)
        border.color: activeFocus ? (onDark ? "#8CB4FF" : root.accent)
                                  : (onDark ? "#294563" : root.line)
        opacity: enabled ? 1 : 0.42
        activeFocusOnTab: true
        Row {
            id: buttonContent
            anchors.centerIn: parent
            spacing: 8
            Text {
                visible: quietButton.glyph.length > 0
                text: quietButton.glyph
                color: quietButton.prominent ? "#FFFFFF"
                                             : (quietButton.onDark ? root.navMuted : root.textSecondary)
                font.pixelSize: 13
                font.weight: Font.DemiBold
            }
            Text {
                text: quietButton.label
                color: quietButton.prominent ? "#FFFFFF"
                                             : (quietButton.onDark ? root.navText : root.textPrimary)
                font.pixelSize: 12
                font.weight: Font.DemiBold
            }
        }
        MouseArea {
            id: buttonMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            enabled: quietButton.enabled
            onPressed: quietButton.forceActiveFocus()
            onClicked: quietButton.clicked()
        }
        Keys.onSpacePressed: clicked()
        Keys.onReturnPressed: clicked()
        Behavior on color { ColorAnimation { duration: 120 } }
        scale: buttonMouse.pressed ? 0.97 : 1
        Behavior on scale { NumberAnimation { duration: 90 } }
    }

    component ToolButton: Rectangle {
        id: toolButton
        property string glyph: ""
        property string tooltip: ""
        property bool selected: false
        property bool onDark: false
        signal clicked()
        implicitWidth: 34
        implicitHeight: 34
        radius: 7
        color: selected ? (onDark ? root.navSoft : root.accentSoft)
                        : (toolMouse.containsMouse
                           ? (onDark ? root.navSoft : root.surfaceSoft) : "transparent")
        border.width: activeFocus ? 2 : (selected ? 1 : 0)
        border.color: activeFocus || selected ? (onDark ? "#8CB4FF" : root.accent)
                                               : "transparent"
        activeFocusOnTab: true
        Text {
            anchors.centerIn: parent
            text: toolButton.glyph
            color: toolButton.onDark ? root.navText
                                     : (toolButton.selected ? root.accent : root.textSecondary)
            font.pixelSize: 14
            font.weight: Font.DemiBold
        }
        MouseArea {
            id: toolMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onPressed: toolButton.forceActiveFocus()
            onClicked: toolButton.clicked()
        }
        Keys.onSpacePressed: clicked()
        Keys.onReturnPressed: clicked()
        ToolTip.visible: toolMouse.containsMouse && tooltip.length > 0
        ToolTip.text: tooltip
        Behavior on color { ColorAnimation { duration: 100 } }
    }

    component MetaPill: Rectangle {
        id: metaPill
        property string label: ""
        property color dotColor: root.textMuted
        implicitWidth: Math.min(pillRow.implicitWidth + 18, 220)
        implicitHeight: 26
        radius: 13
        color: "#F7F8FA"
        border.width: 1
        border.color: root.line
        clip: true
        Row {
            id: pillRow
            anchors.centerIn: parent
            spacing: 7
            Rectangle {
                width: 6
                height: 6
                radius: 3
                color: metaPill.dotColor
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                text: metaPill.label
                width: Math.min(implicitWidth, 188)
                color: root.textSecondary
                font.pixelSize: 9
                font.weight: Font.Medium
                elide: Text.ElideRight
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }

    component ControlSelect: ComboBox {
        id: select
        implicitHeight: 36
        font.pixelSize: 11
        leftPadding: 11
        rightPadding: 34
        contentItem: Text {
            text: select.displayText
            color: root.textPrimary
            font: select.font
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
        indicator: Text {
            text: "⌄"
            color: root.textMuted
            font.pixelSize: 15
            anchors.right: parent.right
            anchors.rightMargin: 12
            anchors.verticalCenter: parent.verticalCenter
        }
        background: Rectangle {
            radius: 7
            color: select.hovered ? root.surfaceSoft : root.surface
            border.width: 1
            border.color: select.activeFocus ? root.accent : root.line
            Behavior on border.color { ColorAnimation { duration: 120 } }
        }
        popup: Popup {
            y: select.height + 6
            width: select.width
            implicitHeight: Math.min(contentItem.implicitHeight + 12, 260)
            padding: 6
            background: Rectangle {
                radius: 9
                color: root.surface
                border.color: root.line
                border.width: 1
            }
            contentItem: ListView {
                clip: true
                implicitHeight: contentHeight
                model: select.popup.visible ? select.delegateModel : null
                currentIndex: select.highlightedIndex
                ScrollIndicator.vertical: ScrollIndicator { }
            }
        }
        delegate: ItemDelegate {
            width: select.width - 12
            height: 36
            contentItem: Text {
                text: modelData
                color: highlighted ? root.textPrimary : root.textSecondary
                font.pixelSize: 12
                verticalAlignment: Text.AlignVCenter
            }
            background: Rectangle {
                radius: 7
                color: highlighted ? root.accentSoft : "transparent"
            }
            highlighted: select.highlightedIndex === index
        }
    }

    component ComposerAction: Rectangle {
        id: composerAction
        property string glyph: ""
        property string label: ""
        property bool active: false
        property string tooltip: ""
        signal clicked()
        implicitWidth: Math.min(actionRow.implicitWidth + 22, 150)
        implicitHeight: 34
        radius: 8
        color: active ? root.accentSoft
                      : (actionMouse.containsMouse ? root.surfaceSoft : "transparent")
        border.width: activeFocus || active ? 1 : 0
        border.color: activeFocus || active ? root.accent : "transparent"
        activeFocusOnTab: true
        clip: true
        Row {
            id: actionRow
            anchors.centerIn: parent
            spacing: 7
            Text {
                text: composerAction.glyph
                color: composerAction.active ? root.accent : root.textMuted
                font.pixelSize: 12
                font.weight: Font.DemiBold
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                text: composerAction.label
                width: Math.min(implicitWidth, 112)
                color: composerAction.active ? root.accent : root.textSecondary
                font.pixelSize: 10
                font.weight: Font.DemiBold
                elide: Text.ElideRight
                anchors.verticalCenter: parent.verticalCenter
            }
        }
        MouseArea {
            id: actionMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onPressed: composerAction.forceActiveFocus()
            onClicked: composerAction.clicked()
        }
        Keys.onSpacePressed: clicked()
        Keys.onReturnPressed: clicked()
        ToolTip.visible: actionMouse.containsMouse && tooltip.length > 0
        ToolTip.text: tooltip
        Behavior on color { ColorAnimation { duration: 110 } }
    }

    component SegmentTab: TabButton {
        id: segmentTab
        implicitHeight: 44
        font.pixelSize: 11
        contentItem: Text {
            text: segmentTab.text
            color: segmentTab.checked ? root.accent : root.textSecondary
            font.pixelSize: segmentTab.font.pixelSize
            font.weight: segmentTab.checked ? Font.DemiBold : Font.Medium
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle {
            color: segmentTab.hovered ? root.surfaceSoft : "transparent"
            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 2
                color: segmentTab.checked ? root.accent : "transparent"
            }
        }
    }

    Shortcut {
        sequences: [StandardKey.New]
        onActivated: controller.newSession()
    }
    Shortcut {
        sequence: "Ctrl+L"
        onActivated: promptInput.forceActiveFocus()
    }
    Shortcut {
        sequence: "Escape"
        onActivated: {
            if (controller && controller.busy)
                controller.cancelRun()
            else if (root.inspectorOpen)
                root.inspectorOpen = false
        }
    }
    Shortcut {
        sequence: "Ctrl+."
        onActivated: root.inspectorOpen = !root.inspectorOpen
    }
    Shortcut {
        sequence: "Ctrl+K"
        onActivated: {
            root.commandOpen = true
            commandCenter.open()
        }
    }
    Shortcut {
        sequences: ["Ctrl+P", "Meta+P"]
        onActivated: modeSelect.popup.open()
    }
    Shortcut {
        sequences: ["Ctrl+M", "Meta+M"]
        onActivated: modelSelect.popup.open()
    }
    Shortcut {
        sequences: ["Ctrl+G", "Meta+G"]
        onActivated: goalPopup.open()
    }

    Connections {
        target: controller
        function onErrorOccurred(message) {
            toastText.text = message
            toast.opacity = 1
            toastTimer.restart()
        }
        function onApprovalRequested(payload) {
            var request = JSON.parse(payload)
            root.approvalId = request.id
            approvalTitle.text = request.tool_call.name + " 请求执行"
            approvalRisk.text = "风险等级  ·  " + request.risk_level
                                + (request.network ? "  ·  将访问网络" : "")
            var sections = []
            if (request.paths && request.paths.length > 0)
                sections.push("访问路径\n" + request.paths.join("\n"))
            if (request.command)
                sections.push("执行命令\n" + (Array.isArray(request.command)
                              ? request.command.join(" ") : request.command))
            sections.push("参数\n" + JSON.stringify(request.tool_call.arguments, null, 2))
            if (request.diff_preview)
                sections.push("变更预览\n" + request.diff_preview)
            approvalDetails.text = sections.join("\n\n")
            approvalDialog.open()
        }
        function onCurrentSessionChanged() {
            if (!controller)
                return
            root.selectValue(providerSelect, controller.currentSessionProvider)
            modelSelect.model = controller.modelsForProvider(providerSelect.currentText)
            root.selectValue(modelSelect, controller.currentSessionModel)
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            id: sidebar
            objectName: "sidebar"
            Layout.preferredWidth: root.width < 1180 ? 220 : 256
            Layout.fillHeight: true
            color: root.nav
            border.width: 0

            ColumnLayout {
                anchors.fill: parent
                anchors.leftMargin: 14
                anchors.rightMargin: 14
                anchors.topMargin: 14
                anchors.bottomMargin: 12
                spacing: 0

                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 40
                    spacing: 10
                    Rectangle {
                        Layout.preferredWidth: 28
                        Layout.preferredHeight: 28
                        radius: 7
                        color: "#8CB4FF"
                        Text {
                            anchors.centerIn: parent
                            text: "YF"
                            color: root.nav
                            font.pixelSize: 11
                            font.weight: Font.Black
                        }
                    }
                    Column {
                        id: emptyState
                        Layout.fillWidth: true
                        spacing: 1
                        Text {
                            text: "YF-Harness"
                            color: root.navText
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                        }
                        Text {
                            text: "LOCAL / PRIVATE"
                            color: root.navMuted
                            font.pixelSize: 7
                            font.letterSpacing: 1.4
                        }
                    }
                    ToolButton {
                        glyph: "+"
                        tooltip: "新建任务  ⌘N"
                        onDark: true
                        onClicked: controller.newSession()
                    }
                }

                TextField {
                    id: sessionSearch
                    Layout.fillWidth: true
                    Layout.topMargin: 12
                    Layout.preferredHeight: 34
                    placeholderText: "搜索任务…"
                    placeholderTextColor: root.navMuted
                    color: root.navText
                    font.pixelSize: 12
                    leftPadding: 31
                    background: Rectangle {
                        radius: 7
                        color: root.navSoft
                        border.width: 1
                        border.color: sessionSearch.activeFocus ? "#8CB4FF" : "#294563"
                    }
                    Text {
                        anchors.left: parent.left
                        anchors.leftMargin: 10
                        anchors.verticalCenter: parent.verticalCenter
                        text: "⌕"
                        color: root.navMuted
                        font.pixelSize: 17
                    }
                    onTextChanged: sessionSearchTimer.restart()
                    Timer {
                        id: sessionSearchTimer
                        interval: 180
                        onTriggered: controller.searchSessions(sessionSearch.text)
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: 18
                    Layout.bottomMargin: 6
                    Text {
                        text: "任务记录"
                        color: root.navMuted
                        font.pixelSize: 10
                        font.weight: Font.DemiBold
                        font.letterSpacing: 1.1
                    }
                    Item { Layout.fillWidth: true }
                    Text {
                        text: sessionList.count
                        color: root.navMuted
                        font.pixelSize: 10
                    }
                }

                ListView {
                    id: sessionList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: 2
                    model: controller ? controller.sessionModel : null
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    delegate: Rectangle {
                        id: sessionRow
                        required property string sessionId
                        required property string title
                        required property string detail
                        required property string updated
                        width: sessionList.width
                        height: 56
                        radius: 7
                        color: controller && controller.currentSessionId === sessionId
                               ? "#FFFFFF"
                               : (sessionMouse.containsMouse ? root.navSoft : "transparent")
                        Rectangle {
                            visible: controller ? controller.currentSessionId === sessionRow.sessionId : false
                            width: 3
                            height: 22
                            radius: 0
                            color: "#6F9FFF"
                            anchors.left: parent.left
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Column {
                            anchors.left: parent.left
                            anchors.leftMargin: 12
                            anchors.right: parent.right
                            anchors.rightMargin: 10
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 4
                            Text {
                                width: parent.width
                                text: sessionRow.title
                                color: controller && controller.currentSessionId === sessionRow.sessionId
                                       ? root.nav : root.navText
                                font.pixelSize: 11
                                font.weight: Font.Medium
                                elide: Text.ElideRight
                            }
                            Row {
                                width: parent.width
                                Text {
                                    width: parent.width - sessionTime.width - 8
                                    text: sessionRow.detail
                                    color: controller && controller.currentSessionId === sessionRow.sessionId
                                           ? root.textSecondary : root.navMuted
                                    font.pixelSize: 8
                                    elide: Text.ElideRight
                                }
                                Text {
                                    id: sessionTime
                                    text: sessionRow.updated
                                    color: controller && controller.currentSessionId === sessionRow.sessionId
                                           ? root.textMuted : root.navMuted
                                    font.pixelSize: 8
                                }
                            }
                        }
                        MouseArea {
                            id: sessionMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: controller.openSession(sessionRow.sessionId)
                        }
                        Behavior on color { ColorAnimation { duration: 130 } }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.topMargin: 10
                    Layout.bottomMargin: 10
                    Layout.preferredHeight: 1
                    color: "#294563"
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 9
                    Rectangle {
                        Layout.preferredWidth: 26
                        Layout.preferredHeight: 26
                        radius: 7
                        color: "#17463E"
                        Text {
                            anchors.centerIn: parent
                            text: "●"
                            color: root.success
                            font.pixelSize: 10
                        }
                    }
                    Column {
                        Layout.fillWidth: true
                        Text { text: "当前项目"; color: root.navText; font.pixelSize: 10; font.weight: Font.Medium }
                        Text {
                            width: sidebar.width - 68
                            text: controller ? controller.workspacePath : ""
                            color: root.navMuted
                            font.pixelSize: 9
                            elide: Text.ElideMiddle
                        }
                    }
                    ToolButton {
                        glyph: "↗"
                        tooltip: "切换项目"
                        onDark: true
                        enabled: controller ? !controller.busy : false
                        onClicked: projectFolderDialog.open()
                    }
                }
                Rectangle {
                    id: sidebarSettings
                    objectName: "sidebarSettings"
                    Layout.fillWidth: true
                    Layout.topMargin: 10
                    Layout.preferredHeight: 46
                    radius: 8
                    color: settingsMouse.containsMouse ? root.navSoft : "transparent"
                    border.width: 1
                    border.color: settingsMouse.containsMouse ? "#3A587A" : "#294563"
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        spacing: 10
                        Text { text: "⚙"; color: root.navMuted; font.pixelSize: 15 }
                        Column {
                            Layout.fillWidth: true
                            spacing: 2
                            Text { text: "设置与用量"; color: root.navText; font.pixelSize: 10; font.weight: Font.Medium }
                            Text { text: "模型 · 模式 · 上下文"; color: root.navMuted; font.pixelSize: 8 }
                        }
                        Text { text: "›"; color: root.navMuted; font.pixelSize: 16 }
                    }
                    MouseArea {
                        id: settingsMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            root.openInspector(0)
                            controller.refreshUsage()
                        }
                    }
                    Behavior on color { ColorAnimation { duration: 120 } }
                }
            }
        }

        Hairline { Layout.fillHeight: true }

        Rectangle {
            id: workspace
            objectName: "workspace"
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: root.canvas

            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 72
                    Layout.leftMargin: 30
                    Layout.rightMargin: 20
                    spacing: 12
                    Column {
                        Layout.fillWidth: true
                        spacing: 4
                        Row {
                            width: parent.width
                            spacing: 6
                            Text {
                                text: "YF /"
                                color: root.accent
                                font.pixelSize: 8
                                font.weight: Font.DemiBold
                                font.letterSpacing: 1.0
                            }
                            Text {
                                width: Math.max(100, Math.min(460, workspace.width - 430))
                                text: controller ? controller.workspacePath : ""
                                color: root.textMuted
                                font.pixelSize: 8
                                elide: Text.ElideMiddle
                            }
                        }
                        Text {
                            objectName: "sessionTitle"
                            width: parent.width
                            text: controller ? controller.currentSessionTitle : ""
                            color: root.textPrimary
                            font.pixelSize: 19
                            font.weight: Font.DemiBold
                            elide: Text.ElideRight
                        }
                    }
                    MetaPill {
                        label: controller ? controller.statusText : ""
                        dotColor: controller && controller.busy ? root.accent : root.success
                    }
                    QuietButton {
                        label: "取消"
                        glyph: "×"
                        visible: controller ? controller.busy : false
                        onClicked: controller.cancelRun()
                    }
                    QuietButton {
                        label: "命令"
                        glyph: "⌘K"
                        visible: workspace.width >= 690
                        onClicked: commandCenter.open()
                    }
                    ToolButton {
                        glyph: root.inspectorOpen ? "×" : "◫"
                        tooltip: root.inspectorOpen ? "关闭检查器" : "打开检查器"
                        selected: root.inspectorOpen
                        visible: !root.inspectorOpen
                        onClicked: root.inspectorOpen = !root.inspectorOpen
                    }
                }

                Hairline { Layout.fillWidth: true }

                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true

                    ListView {
                        id: conversation
                        anchors.fill: parent
                        anchors.leftMargin: Math.max(28, (parent.width - 860) / 2)
                        anchors.rightMargin: Math.max(28, (parent.width - 860) / 2)
                        anchors.topMargin: 34
                        anchors.bottomMargin: 22
                        model: controller ? controller.messageModel : null
                        spacing: 28
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                        onCountChanged: Qt.callLater(positionViewAtEnd)
                        delegate: Item {
                            id: messageDelegate
                            required property string role
                            required property string speaker
                            required property string content
                            required property string timestamp
                            required property bool isUser
                            required property bool isTool
                            required property bool pending
                            width: conversation.width
                            height: contentColumn.height

                            Column {
                                id: contentColumn
                                width: parent.width
                                spacing: 9

                                Row {
                                    anchors.right: messageDelegate.isUser ? parent.right : undefined
                                    spacing: 8
                                    Rectangle {
                                        visible: !messageDelegate.isUser
                                        width: 20
                                        height: 20
                                        radius: 5
                                        color: messageDelegate.pending ? root.accentSoft : root.accent
                                        Text {
                                            anchors.centerIn: parent
                                            text: messageDelegate.pending ? "·" : "Y"
                                            color: messageDelegate.pending ? root.accent : "#FFFFFF"
                                            font.pixelSize: 9
                                            font.weight: Font.Black
                                        }
                                    }
                                    Text {
                                        text: messageDelegate.isUser ? "YOU" : "YF / RESPONSE"
                                        color: messageDelegate.isUser ? root.accent : root.textMuted
                                        font.pixelSize: 8
                                        font.weight: Font.DemiBold
                                        font.letterSpacing: 1.1
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                    Text {
                                        text: messageDelegate.timestamp
                                        color: root.textMuted
                                        font.pixelSize: 8
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                }

                                Rectangle {
                                    visible: !messageDelegate.isTool
                                    anchors.right: messageDelegate.isUser ? parent.right : undefined
                                    width: messageDelegate.isUser
                                           ? Math.min(messageText.implicitWidth + 32, parent.width * 0.78)
                                           : parent.width
                                    height: messageText.implicitHeight + (messageDelegate.isUser ? 22 : 28)
                                    radius: 14
                                    color: messageDelegate.isUser ? root.accent : root.surface
                                    border.width: 1
                                    border.color: messageDelegate.isUser ? root.accent : root.line
                                    Text {
                                        id: messageText
                                        anchors.left: parent.left
                                        anchors.leftMargin: messageDelegate.isUser ? 15 : 20
                                        anchors.right: parent.right
                                        anchors.rightMargin: messageDelegate.isUser ? 15 : 20
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: messageDelegate.content || (messageDelegate.pending ? "正在思考…" : "")
                                        color: messageDelegate.isUser ? "#FFFFFF" : root.textPrimary
                                        font.pixelSize: 14
                                        lineHeight: 1.48
                                        wrapMode: Text.Wrap
                                        textFormat: Text.MarkdownText
                                        onLinkActivated: link => Qt.openUrlExternally(link)
                                    }
                                    Rectangle {
                                        visible: false
                                        anchors.left: parent.left
                                        anchors.top: parent.top
                                        anchors.bottom: parent.bottom
                                        width: 1
                                        color: messageDelegate.pending ? root.accent : root.lineStrong
                                    }
                                }

                                Rectangle {
                                    visible: messageDelegate.isTool
                                    width: parent.width
                                    height: 36
                                    radius: 7
                                    color: root.successSoft
                                    border.color: "#B9DFD1"
                                    border.width: 1
                                    Row {
                                        anchors.fill: parent
                                        anchors.leftMargin: 11
                                        anchors.rightMargin: 11
                                        spacing: 9
                                        Text {
                                            text: messageDelegate.pending ? "◌" : "✓"
                                            color: messageDelegate.pending ? root.accent : root.success
                                            font.pixelSize: 11
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                        Text {
                                            text: messageDelegate.content
                                            color: root.textSecondary
                                            font.pixelSize: 10
                                            anchors.verticalCenter: parent.verticalCenter
                                            width: parent.width - 38
                                            elide: Text.ElideRight
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Item {
                        id: taskEmptyState
                        objectName: "taskEmptyState"
                        visible: conversation.count === 0
                        anchors.centerIn: parent
                        width: Math.min(620, parent.width - 96)
                        height: emptyPrompt.implicitHeight
                        opacity: 0
                        transform: Translate { id: emptyTranslate; y: 10 }
                        Text {
                            id: emptyPrompt
                            anchors.centerIn: parent
                            width: parent.width
                            text: "想做什么？直接说一句就好。"
                            color: root.textPrimary
                            font.pixelSize: 24
                            font.weight: Font.DemiBold
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.Wrap
                        }
                        Component.onCompleted: emptyEntrance.start()
                        ParallelAnimation {
                            id: emptyEntrance
                            NumberAnimation { target: taskEmptyState; property: "opacity"; to: 1; duration: 360; easing.type: Easing.OutCubic }
                            NumberAnimation { target: emptyTranslate; property: "y"; to: 0; duration: 420; easing.type: Easing.OutCubic }
                        }
                    }
                }

                Rectangle {
                    visible: controller ? controller.queueCount > 0 : false
                    Layout.fillWidth: true
                    Layout.leftMargin: Math.max(32, (workspace.width - 820) / 2)
                    Layout.rightMargin: Math.max(32, (workspace.width - 820) / 2)
                    Layout.preferredHeight: 40
                    radius: 8
                    color: root.accentSoft
                    border.color: root.line
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 14
                        anchors.rightMargin: 8
                        spacing: 9
                        Text { text: "≡"; color: root.accent; font.pixelSize: 14 }
                        Text {
                            text: controller ? controller.queueCount + " 个后续任务已排队" : ""
                            color: root.textSecondary
                            font.pixelSize: 11
                        }
                        Item { Layout.fillWidth: true }
                        QuietButton {
                            label: "继续"
                            enabled: controller ? !controller.busy : false
                            onClicked: controller.resumeQueue()
                        }
                        QuietButton {
                            label: "清空"
                            onClicked: controller.clearQueue()
                        }
                    }
                }

                Rectangle {
                    id: skillPalette
                    visible: promptInput.text.trim().startsWith("$")
                             && promptInput.text.indexOf(" ") < 0
                             && controller && controller.skillCount > 0
                    Layout.fillWidth: true
                    Layout.leftMargin: Math.max(32, (workspace.width - 820) / 2)
                    Layout.rightMargin: Math.max(32, (workspace.width - 820) / 2)
                    Layout.preferredHeight: visible ? Math.min(238, 48 + skillList.count * 54) : 0
                    radius: 10
                    color: root.surface
                    border.width: 1
                    border.color: root.lineStrong
                    clip: true

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 4
                        RowLayout {
                            objectName: "taskStatusBar"
                            Layout.fillWidth: true
                            Layout.leftMargin: 8
                            Layout.rightMargin: 8
                            Layout.preferredHeight: 28
                            Text {
                                text: "项目技能"
                                color: root.textPrimary
                                font.pixelSize: 11
                                font.weight: Font.DemiBold
                            }
                            Text {
                                text: "显式调用 · 不自动执行脚本"
                                color: root.textMuted
                                font.pixelSize: 9
                            }
                            Item { Layout.fillWidth: true }
                            Text {
                                text: "↑↓ 选择  ↵ 使用"
                                color: root.textMuted
                                font.pixelSize: 9
                            }
                        }
                        ListView {
                            id: skillList
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            spacing: 3
                            currentIndex: 0
                            model: controller ? controller.skillModel : null
                            delegate: Rectangle {
                                required property int index
                                required property string skillId
                                required property string description
                                required property string source
                                width: skillList.width
                                height: 51
                                radius: 8
                                color: skillList.currentIndex === index || skillMouse.containsMouse
                                       ? root.accentSoft : "transparent"
                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 10
                                    anchors.rightMargin: 10
                                    spacing: 11
                                    Rectangle {
                                        Layout.preferredWidth: 58
                                        Layout.preferredHeight: 23
                                        radius: 6
                                        color: root.accentSoft
                                        Text {
                                            anchors.centerIn: parent
                                            text: source.toUpperCase()
                                            color: root.accent
                                            font.pixelSize: 8
                                            font.weight: Font.DemiBold
                                        }
                                    }
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 2
                                        Text {
                                            Layout.fillWidth: true
                                            text: "$" + skillId
                                            color: root.textPrimary
                                            font.pixelSize: 11
                                            font.weight: Font.DemiBold
                                            elide: Text.ElideRight
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: description
                                            color: root.textMuted
                                            font.pixelSize: 9
                                            elide: Text.ElideRight
                                        }
                                    }
                                }
                                MouseArea {
                                    id: skillMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        promptInput.text = "$" + skillId + " "
                                        promptInput.cursorPosition = promptInput.length
                                        promptInput.forceActiveFocus()
                                    }
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    id: composer
                    objectName: "composer"
                    Layout.fillWidth: true
                    Layout.leftMargin: Math.max(24, (workspace.width - 900) / 2)
                    Layout.rightMargin: Math.max(24, (workspace.width - 900) / 2)
                    Layout.bottomMargin: 20
                    Layout.preferredHeight: controller && controller.attachmentCount > 0 ? 154 : 124
                    radius: 18
                    color: root.surface
                    border.width: 1
                    border.color: promptInput.activeFocus ? root.accent : root.lineStrong

                    Rectangle {
                        anchors.left: parent.left
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        width: 3
                        radius: 1
                        color: promptInput.activeFocus ? root.accent : "transparent"
                        Behavior on color { ColorAnimation { duration: 140 } }
                    }

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 16
                        anchors.rightMargin: 12
                        anchors.topMargin: 12
                        anchors.bottomMargin: 11
                        spacing: 8
                        TextArea {
                            id: promptInput
                            objectName: "promptInput"
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            placeholderText: "描述要完成的任务，或按 ⌘K 打开命令中心…"
                            placeholderTextColor: root.textMuted
                            color: root.textPrimary
                            selectionColor: root.accent
                            selectedTextColor: root.canvas
                            font.pixelSize: 13
                            wrapMode: TextEdit.Wrap
                            background: Item { }
                            onTextChanged: {
                                if (controller && text.trim().startsWith("$")
                                        && text.indexOf(" ") < 0) {
                                    controller.filterSkills(text)
                                    skillList.currentIndex = 0
                                }
                            }
                            Keys.onPressed: event => {
                                var modifier = (event.modifiers & Qt.ControlModifier) || (event.modifiers & Qt.MetaModifier)
                                if (modifier && (event.key === Qt.Key_Return || event.key === Qt.Key_Enter)) {
                                    root.sendCurrentPrompt()
                                    event.accepted = true
                                } else if (skillPalette.visible && event.key === Qt.Key_Down) {
                                    skillList.currentIndex = Math.min(skillList.count - 1,
                                                                      skillList.currentIndex + 1)
                                    event.accepted = true
                                } else if (skillPalette.visible && event.key === Qt.Key_Up) {
                                    skillList.currentIndex = Math.max(0, skillList.currentIndex - 1)
                                    event.accepted = true
                                } else if (skillPalette.visible
                                           && (event.key === Qt.Key_Tab
                                               || event.key === Qt.Key_Return
                                               || event.key === Qt.Key_Enter)) {
                                    var selectedSkill = controller.skillIdAt(skillList.currentIndex)
                                    if (selectedSkill.length > 0) {
                                        text = "$" + selectedSkill + " "
                                        cursorPosition = length
                                    }
                                    event.accepted = true
                                }
                            }
                        }
                        ListView {
                            visible: controller ? controller.attachmentCount > 0 : false
                            Layout.fillWidth: true
                            Layout.preferredHeight: visible ? 29 : 0
                            orientation: ListView.Horizontal
                            spacing: 7
                            clip: true
                            model: controller ? controller.attachmentModel : null
                            delegate: Rectangle {
                                required property string attachmentId
                                required property string name
                                required property string transfer
                                width: attachmentLabel.implicitWidth + 34
                                height: 27
                                radius: 8
                                color: root.surfaceSoft
                                border.color: root.line
                                Text {
                                    id: attachmentLabel
                                    anchors.left: parent.left
                                    anchors.leftMargin: 10
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: name + " · " + transfer
                                    color: root.textSecondary
                                    font.pixelSize: 9
                                }
                                Text {
                                    anchors.right: parent.right
                                    anchors.rightMargin: 8
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: "×"
                                    color: attachmentMouse.containsMouse ? root.textPrimary : root.textMuted
                                    font.pixelSize: 13
                                }
                                MouseArea {
                                    id: attachmentMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: controller.removeAttachment(attachmentId)
                                }
                            }
                        }
                        RowLayout {
                            objectName: "composerActions"
                            Layout.fillWidth: true
                            Layout.preferredHeight: 32
                            spacing: 7
                            ToolButton {
                                id: attachmentButton
                                objectName: "attachmentButton"
                                glyph: "+"
                                tooltip: "添加图片或文件"
                                onClicked: attachmentMenu.open()
                            }
                            ControlSelect {
                                id: modeSelect
                                objectName: "composerModeSelect"
                                Layout.preferredWidth: 102
                                implicitHeight: 34
                                model: ["agent", "plan", "chat", "review"]
                                currentIndex: 0
                                ToolTip.visible: hovered
                                ToolTip.text: "运行模式  ·  ⌘P"
                            }
                            ControlSelect {
                                id: modelSelect
                                objectName: "composerModelSelect"
                                Layout.preferredWidth: Math.min(176, Math.max(132, composer.width * 0.2))
                                implicitHeight: 34
                                ToolTip.visible: hovered
                                ToolTip.text: controller ? controller.modelDescription(currentText) + "  ·  ⌘M" : "模型"
                            }
                            ComposerAction {
                                objectName: "composerGoalButton"
                                glyph: "◎"
                                label: controller && controller.hasActiveGoal ? "目标进行中" : "目标"
                                active: controller ? controller.hasActiveGoal : false
                                tooltip: controller && controller.hasActiveGoal
                                         ? controller.currentGoal : "设置持久目标  ·  ⌘G"
                                onClicked: goalPopup.open()
                            }
                            ComposerAction {
                                objectName: "composerContextButton"
                                glyph: "◔"
                                label: controller && controller.contextBudget > 0
                                       ? Math.round(controller.contextUsageRatio * 100) + "% 上下文"
                                       : "上下文"
                                active: controller ? controller.contextUsageRatio >= 0.8 : false
                                tooltip: controller ? controller.contextSummary : "查看上下文"
                                onClicked: root.openInspector(1)
                            }
                            Item { Layout.fillWidth: true }
                            QuietButton {
                                objectName: "sendButton"
                                label: controller && controller.busy ? "排队" : "发送"
                                glyph: controller && controller.busy ? "+" : "↗"
                                prominent: true
                                enabled: controller ? promptInput.text.trim().length > 0 : false
                                onClicked: root.sendCurrentPrompt()
                            }
                            Menu {
                                id: attachmentMenu
                                y: -height - 8
                                width: 176
                                MenuItem {
                                    text: "添加图片"
                                    onTriggered: imageDialog.open()
                                }
                                MenuItem {
                                    text: "添加文件"
                                    onTriggered: fileDialog.open()
                                }
                                MenuSeparator { }
                                MenuItem {
                                    text: "管理 Skills"
                                    onTriggered: {
                                        controller.filterSkills("$")
                                        skillsDialog.open()
                                    }
                                }
                                MenuItem {
                                    text: "工具与连接"
                                    onTriggered: connectionsDialog.open()
                                }
                            }
                        }

                        Item {
                            Layout.preferredWidth: 0
                            Layout.preferredHeight: 0
                            Popup {
                                id: goalPopup
                            parent: Overlay.overlay
                            x: Math.max(20, (root.width - width) / 2)
                            y: root.height - height - 170
                            width: Math.min(430, root.width - 40)
                            padding: 14
                            closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
                            onOpened: {
                                goalInput.text = controller ? controller.currentGoal : ""
                                goalInput.forceActiveFocus()
                            }
                            background: Rectangle {
                                radius: 12
                                color: root.surface
                                border.color: root.lineStrong
                                border.width: 1
                            }
                                contentItem: ColumnLayout {
                                spacing: 10
                                Text {
                                    Layout.fillWidth: true
                                    text: "持久目标"
                                    color: root.textPrimary
                                    font.pixelSize: 13
                                    font.weight: Font.DemiBold
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: "后续每次运行都会看到这个目标，但权限与审批不会改变。"
                                    color: root.textMuted
                                    font.pixelSize: 9
                                    wrapMode: Text.Wrap
                                }
                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 92
                                    radius: 8
                                    color: "#F8F9FB"
                                    border.color: goalInput.activeFocus ? root.accent : root.line
                                    TextArea {
                                        id: goalInput
                                        objectName: "goalEditor"
                                        anchors.fill: parent
                                        anchors.margins: 8
                                        placeholderText: "例如：完成桌面 App 的 0.8 发布"
                                        placeholderTextColor: root.textMuted
                                        color: root.textPrimary
                                        font.pixelSize: 11
                                        wrapMode: TextEdit.Wrap
                                        background: Item { }
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    Text {
                                        text: controller && controller.goalStatus === "completed"
                                              ? "已完成" : (controller && controller.hasActiveGoal
                                                            ? "进行中" : "未设置")
                                        color: controller && controller.hasActiveGoal
                                               ? root.success : root.textMuted
                                        font.pixelSize: 9
                                    }
                                    Item { Layout.fillWidth: true }
                                    QuietButton {
                                        label: "清除"
                                        enabled: controller ? controller.currentGoal.length > 0 : false
                                        onClicked: {
                                            controller.clearGoal()
                                            goalPopup.close()
                                        }
                                    }
                                    QuietButton {
                                        label: "完成"
                                        enabled: controller ? controller.hasActiveGoal : false
                                        onClicked: {
                                            controller.completeGoal()
                                            goalPopup.close()
                                        }
                                    }
                                    QuietButton {
                                        label: "保存目标"
                                        prominent: true
                                        enabled: goalInput.text.trim().length > 0
                                        onClicked: {
                                            controller.setGoal(goalInput.text)
                                            goalPopup.close()
                                        }
                                    }
                                }
                                }
                            }
                        }

                    }
                    Behavior on border.color { ColorAnimation { duration: 150 } }
                }
            }
        }

        Hairline {
            Layout.fillHeight: true
            visible: false
        }

        Item {
            Layout.preferredWidth: 0
            Layout.preferredHeight: 0
            Popup {
                id: inspector
            objectName: "inspector"
            parent: Overlay.overlay
            visible: root.inspectorOpen
            modal: false
            dim: false
            x: parent.width - width
            y: 0
            width: root.width >= 1320 ? 360 : 330
            height: parent.height
            padding: 0
            z: 30
            closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
            onClosed: root.inspectorOpen = false
            background: Rectangle {
                radius: 18
                color: root.surface
                border.color: root.lineStrong
                border.width: 1
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 14
                spacing: 0
                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        text: "设置与用量"
                        color: root.textPrimary
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                    }
                    Item { Layout.fillWidth: true }
                    Text {
                        text: controller && controller.busy ? "●  LIVE" : "LOCAL"
                        color: controller && controller.busy ? root.accent : root.textMuted
                        font.pixelSize: 9
                        font.letterSpacing: 0.8
                    }
                    ToolButton {
                        glyph: "×"
                        tooltip: "关闭设置"
                        onClicked: root.inspectorOpen = false
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: 14
                    spacing: 3
                    Repeater {
                        model: ["设置", "上下文", "变更"]
                        Rectangle {
                            required property string modelData
                            required property int index
                            Layout.fillWidth: true
                            height: 32
                            radius: 6
                            color: root.inspectorTab === index ? root.raised : "transparent"
                            Text {
                                anchors.centerIn: parent
                                text: modelData
                                color: root.inspectorTab === index ? root.textPrimary : root.textMuted
                                font.pixelSize: 10
                                font.weight: root.inspectorTab === index ? Font.DemiBold : Font.Normal
                            }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.inspectorTab = index
                            }
                            Behavior on color { ColorAnimation { duration: 120 } }
                        }
                    }
                }

                StackLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.topMargin: 16
                    currentIndex: root.inspectorTab

                    ScrollView {
                        clip: true
                        contentWidth: availableWidth
                        ColumnLayout {
                            width: parent.width
                            spacing: 0
                            RowLayout {
                                Layout.fillWidth: true
                                Text {
                                    text: "本地用量与额度"
                                    color: root.textPrimary
                                    font.pixelSize: 12
                                    font.weight: Font.DemiBold
                                }
                                Item { Layout.fillWidth: true }
                                ToolButton {
                                    glyph: "↻"
                                    tooltip: "刷新本地用量"
                                    onClicked: controller.refreshUsage()
                                }
                            }
                            Text {
                                Layout.fillWidth: true
                                Layout.topMargin: 6
                                text: "只统计本机保存的运行记录，不代表 Provider 账户余额。"
                                color: root.textMuted
                                font.pixelSize: 9
                                wrapMode: Text.Wrap
                            }
                            Repeater {
                                model: controller ? controller.usageModel : null
                                delegate: Rectangle {
                                    required property string label
                                    required property int tokens
                                    required property int runs
                                    required property int estimated
                                    required property string cost
                                    required property string budget
                                    required property real ratio
                                    Layout.fillWidth: true
                                    Layout.topMargin: 10
                                    implicitHeight: usageColumn.implicitHeight + 22
                                    radius: 10
                                    color: root.surfaceSoft
                                    ColumnLayout {
                                        id: usageColumn
                                        anchors.fill: parent
                                        anchors.margins: 11
                                        spacing: 5
                                        RowLayout {
                                            Layout.fillWidth: true
                                            Text { text: label; color: root.textPrimary; font.pixelSize: 10; font.weight: Font.DemiBold }
                                            Item { Layout.fillWidth: true }
                                            Text { text: tokens.toLocaleString() + " tokens"; color: root.accent; font.pixelSize: 10; font.weight: Font.DemiBold }
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: runs + " 次运行 · 估算 " + estimated.toLocaleString() + " · " + cost
                                            color: root.textSecondary
                                            font.pixelSize: 9
                                            elide: Text.ElideRight
                                        }
                                        Rectangle {
                                            Layout.fillWidth: true
                                            height: 5
                                            radius: 3
                                            color: root.line
                                            Rectangle {
                                                width: parent.width * ratio
                                                height: parent.height
                                                radius: 3
                                                color: ratio >= 0.9 ? root.danger : root.accent
                                            }
                                        }
                                        Text { text: budget; color: root.textMuted; font.pixelSize: 8 }
                                    }
                                }
                            }
                            Hairline { Layout.fillWidth: true; Layout.topMargin: 18; Layout.bottomMargin: 16 }
                            Text { text: "模型来源"; color: root.textMuted; font.pixelSize: 9; font.letterSpacing: 0.8 }
                            ControlSelect {
                                id: providerSelect
                                Layout.fillWidth: true
                                Layout.topMargin: 7
                                model: controller ? controller.providerOptions : []
                                onActivated: {
                                    modelSelect.model = controller.modelsForProvider(currentText)
                                    modelSelect.currentIndex = 0
                                }
                            }
                            Text { Layout.topMargin: 14; text: "模型"; color: root.textMuted; font.pixelSize: 9; font.letterSpacing: 0.8 }
                            Text {
                                Layout.fillWidth: true
                                Layout.topMargin: 7
                                text: modelSelect.currentText.length > 0
                                      ? modelSelect.currentText + "  ·  可在输入框直接切换"
                                      : "当前 Provider 没有可用模型"
                                color: root.textSecondary
                                font.pixelSize: 10
                                elide: Text.ElideRight
                            }
                            Text { Layout.topMargin: 14; text: "工作流"; color: root.textMuted; font.pixelSize: 9; font.letterSpacing: 0.8 }
                            ControlSelect {
                                id: workflowSelect
                                Layout.fillWidth: true
                                Layout.topMargin: 7
                                model: controller ? controller.workflowOptions : []
                                onActivated: {
                                    root.selectValue(modeSelect, controller.workflowMode(currentText))
                                    root.selectValue(permissionSelect, controller.workflowPermissions(currentText))
                                }
                            }
                            Text {
                                Layout.fillWidth: true
                                Layout.topMargin: 7
                                text: controller && workflowSelect.currentText.length > 0
                                      ? controller.workflowDescription(workflowSelect.currentText) : ""
                                color: root.textMuted
                                font.pixelSize: 9
                                wrapMode: Text.Wrap
                            }
                            Text { Layout.topMargin: 14; text: "运行模式"; color: root.textMuted; font.pixelSize: 9; font.letterSpacing: 0.8 }
                            Text {
                                Layout.fillWidth: true
                                Layout.topMargin: 7
                                text: modeSelect.currentText + "  ·  可在输入框直接切换"
                                color: root.textSecondary
                                font.pixelSize: 10
                            }
                            Text { Layout.topMargin: 14; text: "权限策略"; color: root.textMuted; font.pixelSize: 9; font.letterSpacing: 0.8 }
                            ControlSelect {
                                id: permissionSelect
                                Layout.fillWidth: true
                                Layout.topMargin: 7
                                model: ["safe_auto", "always_ask", "deny_writes"]
                                currentIndex: 0
                            }
                            Switch {
                                id: sendImageSwitch
                                Layout.fillWidth: true
                                Layout.topMargin: 16
                                text: "允许把所选图片发送给远程模型"
                                checked: false
                                font.pixelSize: 10
                                palette.text: root.textSecondary
                                ToolTip.visible: hovered
                                ToolTip.text: checked
                                              ? "新选择的图片会在发送前再次校验"
                                              : "默认仅在本地记录图片，不上传内容"
                            }

                            Rectangle {
                                visible: controller ? controller.hasExecutablePlan : false
                                Layout.fillWidth: true
                                Layout.topMargin: 20
                                implicitHeight: planColumn.implicitHeight + 24
                                radius: 11
                                        color: root.accentSoft
                                        border.color: "#B9CBF4"
                                ColumnLayout {
                                    id: planColumn
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.top: parent.top
                                    anchors.margins: 12
                                    spacing: 8
                                    Text { text: "已审阅计划"; color: root.accent; font.pixelSize: 10; font.weight: Font.DemiBold }
                                    Text {
                                        Layout.fillWidth: true
                                        text: controller ? controller.lastPlanPreview : ""
                                        color: root.textSecondary
                                        font.pixelSize: 10
                                        wrapMode: Text.Wrap
                                        maximumLineCount: 5
                                        elide: Text.ElideRight
                                    }
                                    QuietButton {
                                        Layout.fillWidth: true
                                        label: controller && controller.busy ? "加入执行队列" : "执行此计划"
                                        glyph: "▶"
                                        onClicked: controller.executeLastPlan(
                                            providerSelect.currentText,
                                            modelSelect.currentText,
                                            workflowSelect.currentText,
                                            permissionSelect.currentText
                                        )
                                    }
                                }
                            }

                            Hairline { Layout.fillWidth: true; Layout.topMargin: 22; Layout.bottomMargin: 18 }
                            Text { text: "安全边界"; color: root.textPrimary; font.pixelSize: 12; font.weight: Font.Medium }
                            Text {
                                Layout.fillWidth: true
                                Layout.topMargin: 8
                                text: "写入、Shell 与高风险工具执行前审批；路径限制在工作区。"
                                color: root.textSecondary
                                font.pixelSize: 10
                                lineHeight: 1.45
                                wrapMode: Text.Wrap
                            }
                            Row {
                                Layout.topMargin: 14
                                spacing: 7
                                Rectangle { width: 7; height: 7; radius: 4; color: root.success; anchors.verticalCenter: parent.verticalCenter }
                                Text { text: "WorkspaceGuard 已启用"; color: root.textSecondary; font.pixelSize: 10 }
                            }
                            QuietButton {
                                Layout.fillWidth: true
                                Layout.topMargin: 20
                                label: "分支当前会话"
                                glyph: "⑂"
                                enabled: controller ? !controller.busy && controller.currentSessionId.length > 0 : false
                                onClicked: controller.forkSession()
                            }
                        }
                    }

                    Item {
                        ColumnLayout {
                            anchors.fill: parent
                            spacing: 8
                            Text {
                                Layout.fillWidth: true
                                text: controller ? controller.contextSummary : ""
                                color: root.textMuted
                                font.pixelSize: 9
                            }
                            QuietButton {
                                Layout.fillWidth: true
                                label: controller && controller.contextCompacted
                                       ? "重新压缩当前会话" : "立即压缩当前会话"
                                glyph: "◫"
                                enabled: controller ? !controller.busy && controller.currentSessionId.length > 0 : false
                                onClicked: controller.compactContext()
                            }
                            Text {
                                Layout.fillWidth: true
                                text: controller && controller.contextCompactionStatus === "reused"
                                      ? "本次运行已复用持久化摘要"
                                      : (controller && controller.contextCompactionStatus === "created"
                                         ? "本次运行自动生成了新摘要"
                                         : (controller && controller.contextCompactionStatus === "manual"
                                            ? "摘要已手动更新，将在下次运行复用"
                                            : (controller && controller.contextCompactionStatus === "stored"
                                               ? "已有持久化摘要，将在下次运行复用" : "尚未压缩")))
                                color: root.textSecondary
                                font.pixelSize: 9
                                wrapMode: Text.Wrap
                            }
                        ListView {
                            id: instructionList
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            spacing: 0
                            model: controller ? controller.instructionModel : null
                            delegate: Rectangle {
                                required property string source
                                required property string label
                                required property string path
                                required property string scope
                                required property int tokens
                                width: ListView.view.width
                                height: 82
                                color: "transparent"
                                Column {
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.verticalCenter: parent.verticalCenter
                                    spacing: 5
                                    Row {
                                        spacing: 7
                                        Rectangle { width: 6; height: 6; radius: 3; color: root.accent; anchors.verticalCenter: parent.verticalCenter }
                                        Text { text: label; color: root.textPrimary; font.pixelSize: 11; font.weight: Font.Medium }
                                    }
                                    Text { width: parent.width; text: path; color: root.textSecondary; font.pixelSize: 9; elide: Text.ElideMiddle }
                                    Text { text: scope + " · ≈" + tokens + " tokens"; color: root.textMuted; font.pixelSize: 9 }
                                }
                                Hairline { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom }
                            }
                            footer: Text {
                                width: parent ? parent.width : 0
                                topPadding: 14
                                text: instructionList.count === 0 ? "未发现项目规则文件" : "按低 → 高优先级注入上下文"
                                color: root.textMuted
                                font.pixelSize: 9
                                wrapMode: Text.Wrap
                            }
                        }
                        }
                    }

                    Item {
                        ListView {
                            id: changeList
                            anchors.fill: parent
                            clip: true
                            spacing: 0
                            model: controller ? controller.changeModel : null
                            delegate: Rectangle {
                                id: changeRow
                                required property string changeId
                                required property string runId
                                required property string path
                                required property string summary
                                required property string diff
                                required property string status
                                required property bool canRestore
                                required property string created
                                property bool expanded: false
                                width: ListView.view.width
                                height: expanded ? 324 : 88
                                color: "transparent"
                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.topMargin: 12
                                    anchors.bottomMargin: 12
                                    spacing: 5
                                    RowLayout {
                                        Layout.fillWidth: true
                                        Text { text: changeRow.summary; color: changeRow.status === "undone" ? root.textMuted : root.accent; font.pixelSize: 10; font.weight: Font.DemiBold }
                                        Item { Layout.fillWidth: true }
                                        Text { text: changeRow.expanded ? "⌃" : "⌄"; color: root.textMuted; font.pixelSize: 12 }
                                    }
                                    Text { Layout.fillWidth: true; text: changeRow.path; color: root.textPrimary; font.pixelSize: 10; elide: Text.ElideMiddle }
                                    Text {
                                        visible: changeRow.expanded && changeRow.runId.length > 0
                                        text: "RUN " + changeRow.runId.slice(0, 8)
                                        color: root.textMuted
                                        font.pixelSize: 8
                                        font.letterSpacing: 0.7
                                    }
                                    Rectangle {
                                        visible: changeRow.expanded
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 156
                                        radius: 8
                                        color: "#F7F8FA"
                                        ScrollView {
                                            anchors.fill: parent
                                            anchors.margins: 9
                                            TextArea {
                                                text: changeRow.diff
                                                readOnly: true
                                                color: root.textSecondary
                                                font.family: "Menlo"
                                                font.pixelSize: 9
                                                wrapMode: TextEdit.NoWrap
                                                background: Item { }
                                            }
                                        }
                                    }
                                    QuietButton {
                                        visible: changeRow.expanded
                                        Layout.fillWidth: true
                                        label: changeRow.status === "undone" ? "已撤销" : "安全撤销此变更"
                                        glyph: "↶"
                                        enabled: changeRow.canRestore && !(controller && controller.busy)
                                        onClicked: controller.restoreChange(changeRow.changeId)
                                    }
                                    QuietButton {
                                        visible: changeRow.expanded && changeRow.runId.length > 0
                                        Layout.fillWidth: true
                                        label: "撤销本次运行全部变更"
                                        glyph: "↶"
                                        enabled: changeRow.canRestore && !(controller && controller.busy)
                                        onClicked: controller.restoreRun(changeRow.runId)
                                    }
                                }
                                MouseArea {
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.top: parent.top
                                    height: 78
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: changeRow.expanded = !changeRow.expanded
                                }
                                Hairline { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom }
                                Behavior on height { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
                            }
                            footer: Text {
                                width: parent ? parent.width : 0
                                topPadding: 14
                                text: changeList.count === 0 ? "本会话尚无文件变更" : "撤销前会校验文件哈希，避免覆盖后续编辑"
                                color: root.textMuted
                                font.pixelSize: 9
                                wrapMode: Text.Wrap
                            }
                        }
                    }
                }

                QuietButton {
                    Layout.fillWidth: true
                    Layout.topMargin: 10
                    label: "刷新配置"
                    glyph: "↻"
                    onClicked: {
                        controller.reloadConfiguration()
                        root.selectValue(providerSelect, controller.defaultProvider)
                        root.selectValue(workflowSelect, controller.defaultWorkflow)
                    }
                }
                Text {
                    Layout.fillWidth: true
                    Layout.topMargin: 10
                    text: "YF-Harness 0.12.0 · Local first"
                    color: root.textMuted
                    font.pixelSize: 9
                    horizontalAlignment: Text.AlignHCenter
                }
            }

            Component.onCompleted: {
                root.selectValue(providerSelect, controller.defaultProvider)
                modelSelect.model = controller.modelsForProvider(providerSelect.currentText)
                root.selectValue(modelSelect, controller.defaultModel)
                root.selectValue(workflowSelect, controller.defaultWorkflow)
                root.selectValue(modeSelect, controller.workflowMode(workflowSelect.currentText))
                root.selectValue(permissionSelect,
                                 controller.workflowPermissions(workflowSelect.currentText))
            }
            enter: Transition {
                NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 150 }
                NumberAnimation { property: "x"; from: root.width; to: root.width - inspector.width; duration: 210; easing.type: Easing.OutCubic }
            }
                exit: Transition {
                    NumberAnimation { property: "opacity"; from: 1; to: 0; duration: 120 }
                }
            }
        }
    }

    Popup {
        id: commandCenter
        objectName: "commandCenter"
        parent: Overlay.overlay
        x: Math.max(20, (root.width - width) / 2)
        y: Math.max(28, Math.min(92, root.height * 0.11))
        width: Math.min(620, root.width - 40)
        height: Math.min(580, root.height - 56)
        padding: 0
        modal: true
        dim: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        onOpened: {
            root.commandOpen = true
            commandQuery.clear()
            commandList.currentIndex = 0
            commandQuery.forceActiveFocus()
        }
        onClosed: root.commandOpen = false
        Overlay.modal: Rectangle { color: "#5A10223D" }
        background: Rectangle {
            radius: 20
            color: root.surface
            border.width: 1
            border.color: root.lineStrong
        }
        contentItem: ColumnLayout {
            spacing: 0
            RowLayout {
                Layout.fillWidth: true
                Layout.preferredHeight: 72
                Layout.leftMargin: 20
                Layout.rightMargin: 16
                spacing: 12
                Rectangle {
                    Layout.preferredWidth: 34
                    Layout.preferredHeight: 34
                    radius: 10
                    color: root.accentSoft
                    Text {
                        anchors.centerIn: parent
                        text: "⌘"
                        color: root.accent
                        font.pixelSize: 15
                        font.weight: Font.DemiBold
                    }
                }
                TextField {
                    id: commandQuery
                    objectName: "commandQuery"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 46
                    placeholderText: "搜索动作、视图或工作流…"
                    placeholderTextColor: root.textMuted
                    color: root.textPrimary
                    font.pixelSize: 15
                    leftPadding: 0
                    rightPadding: 0
                    background: Item { }
                    onTextChanged: Qt.callLater(root.selectFirstMatchingCommand)
                    Keys.onPressed: event => {
                        if (event.key === Qt.Key_Down) {
                            root.moveCommandSelection(1)
                            event.accepted = true
                        } else if (event.key === Qt.Key_Up) {
                            root.moveCommandSelection(-1)
                            event.accepted = true
                        } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                            var item = commandList.itemAtIndex(commandList.currentIndex)
                            if (item)
                                root.runCommand(item.actionId)
                            event.accepted = true
                        }
                    }
                }
                Rectangle {
                    Layout.preferredWidth: 34
                    Layout.preferredHeight: 24
                    radius: 6
                    color: root.surfaceSoft
                    Text { anchors.centerIn: parent; text: "ESC"; color: root.textMuted; font.pixelSize: 8 }
                }
            }
            Hairline { Layout.fillWidth: true }
            Text {
                Layout.fillWidth: true
                Layout.leftMargin: 20
                Layout.topMargin: 14
                Layout.bottomMargin: 8
                text: "工作台命令"
                color: root.textMuted
                font.pixelSize: 9
                font.weight: Font.DemiBold
                font.letterSpacing: 1.0
            }
            ListView {
                id: commandList
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.leftMargin: 10
                Layout.rightMargin: 10
                Layout.bottomMargin: 10
                clip: true
                spacing: 3
                currentIndex: 0
                model: ListModel {
                    ListElement { actionId: "new"; glyph: "+"; title: "新建任务"; detail: "清空画布并开始一个独立会话"; shortcut: "⌘N" }
                    ListElement { actionId: "plan"; glyph: "◇"; title: "切换到 Plan"; detail: "只读分析并生成可审阅计划"; shortcut: "P" }
                    ListElement { actionId: "goal"; glyph: "◎"; title: "设置持久目标"; detail: "为后续运行保留当前任务方向"; shortcut: "G" }
                    ListElement { actionId: "changes"; glyph: "△"; title: "审查文件变更"; detail: "查看 Diff 并安全撤销文件或整次运行"; shortcut: "R" }
                    ListElement { actionId: "context"; glyph: "◔"; title: "查看上下文"; detail: "检查 Token 预算、规则来源与压缩状态"; shortcut: "C" }
                    ListElement { actionId: "usage"; glyph: "∑"; title: "用量与额度"; detail: "查看会话、今日与本月本地 Token/成本账本"; shortcut: "U" }
                    ListElement { actionId: "skills"; glyph: "$"; title: "Skills 管理与调用"; detail: "创建、导入、安装并调用项目技能"; shortcut: "S" }
                    ListElement { actionId: "connections"; glyph: "⌘"; title: "工具与连接"; detail: "管理联网 MCP、凭据与内置工具状态"; shortcut: "M" }
                    ListElement { actionId: "github"; glyph: "◇"; title: "GitHub 仓库"; detail: "同步分支并查看 PR、Issue 与 Actions"; shortcut: "H" }
                    ListElement { actionId: "project"; glyph: "↗"; title: "切换项目"; detail: "选择另一个本地工作区"; shortcut: "O" }
                }
                delegate: Rectangle {
                    id: commandRow
                    required property int index
                    required property string actionId
                    required property string glyph
                    required property string title
                    required property string detail
                    required property string shortcut
                    property bool queryMatch: commandQuery.text.length === 0
                                              || title.toLowerCase().indexOf(commandQuery.text.toLowerCase()) >= 0
                                              || detail.toLowerCase().indexOf(commandQuery.text.toLowerCase()) >= 0
                    width: ListView.view.width
                    height: queryMatch ? 58 : 0
                    visible: height > 0
                    radius: 12
                    color: commandList.currentIndex === index || commandMouse.containsMouse
                           ? root.accentSoft : "transparent"
                    clip: true
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 12
                        spacing: 12
                        Rectangle {
                            Layout.preferredWidth: 32
                            Layout.preferredHeight: 32
                            radius: 9
                            color: commandList.currentIndex === commandRow.index
                                   ? root.accent : root.surfaceSoft
                            Text {
                                anchors.centerIn: parent
                                text: commandRow.glyph
                                color: commandList.currentIndex === commandRow.index
                                       ? "#FFFFFF" : root.textSecondary
                                font.pixelSize: 13
                                font.weight: Font.DemiBold
                            }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2
                            Text {
                                Layout.fillWidth: true
                                text: commandRow.title
                                color: root.textPrimary
                                font.pixelSize: 12
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                            }
                            Text {
                                Layout.fillWidth: true
                                text: commandRow.detail
                                color: root.textMuted
                                font.pixelSize: 9
                                elide: Text.ElideRight
                            }
                        }
                        Text {
                            text: commandRow.shortcut
                            color: root.textMuted
                            font.pixelSize: 9
                        }
                    }
                    QuietButton {
                        Layout.topMargin: 8
                        label: "打开 GitHub 仓库工作区"
                        glyph: "◇"
                        onClicked: {
                            connectionsDialog.close()
                            controller.refreshGitHub()
                            githubDialog.open()
                        }
                    }
                    MouseArea {
                        id: commandMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onEntered: commandList.currentIndex = commandRow.index
                        onClicked: root.runCommand(commandRow.actionId)
                    }
                    Behavior on color { ColorAnimation { duration: 100 } }
                }
            }
            Text {
                Layout.fillWidth: true
                Layout.leftMargin: 20
                Layout.rightMargin: 20
                Layout.bottomMargin: 16
                text: "↑↓ 选择  ·  ↵ 执行  ·  所有动作继续遵守当前权限与审批"
                color: root.textMuted
                font.pixelSize: 9
                elide: Text.ElideRight
            }
        }
    }

    FileDialog {
        id: imageDialog
        title: "选择项目内的图片"
        fileMode: FileDialog.OpenFiles
        nameFilters: ["Images (*.png *.jpg *.jpeg *.gif *.webp)"]
        onAccepted: {
            for (var index = 0; index < selectedFiles.length; index++)
                controller.addImage(selectedFiles[index].toString(), sendImageSwitch.checked)
        }
    }

    FileDialog {
        id: fileDialog
        title: "选择项目内的文件"
        fileMode: FileDialog.OpenFiles
        nameFilters: [
            "文本与代码 (*.txt *.md *.py *.js *.ts *.tsx *.jsx *.json *.toml *.yaml *.yml *.xml *.html *.css *.csv *.log *.ini *.cfg *.sh)",
            "所有文件 (*)"
        ]
        onAccepted: {
            for (var index = 0; index < selectedFiles.length; index++)
                controller.addFile(selectedFiles[index].toString())
        }
    }

    FolderDialog {
        id: projectFolderDialog
        title: "选择 YF-Harness 项目文件夹"
        onAccepted: controller.setWorkspace(selectedFolder.toString())
    }

    FolderDialog {
        id: skillFolderDialog
        title: "选择包含 SKILL.md 的文件夹"
        onAccepted: controller.importProjectSkill(selectedFolder.toString())
    }

    Dialog {
        id: skillsDialog
        objectName: "skillsDialog"
        anchors.centerIn: parent
        width: Math.min(700, root.width - 80)
        modal: true
        closePolicy: Popup.CloseOnEscape
        padding: 0
        background: Rectangle {
            radius: 16
            color: root.surface
            border.color: root.lineStrong
            border.width: 1
        }
        contentItem: ColumnLayout {
            spacing: 0
            ColumnLayout {
                Layout.fillWidth: true
                Layout.margins: 22
                spacing: 5
                Text { text: "Skills"; color: root.textPrimary; font.pixelSize: 18; font.weight: Font.DemiBold }
                Text {
                    text: controller ? controller.skillCount + " 个项目 Skill 可用  ·  $ 可直接调用" : ""
                    color: root.textMuted
                    font.pixelSize: 10
                }
            }
            TabBar {
                id: skillTabs
                Layout.fillWidth: true
                background: Rectangle { color: "transparent" }
                SegmentTab { text: "已安装" }
                SegmentTab { text: "新建 / 导入" }
                SegmentTab { text: "从 GitHub 安装" }
            }
            Hairline { Layout.fillWidth: true }
            StackLayout {
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(470, root.height - 270)
                currentIndex: skillTabs.currentIndex
                Item {
                    ListView {
                        anchors.fill: parent
                        anchors.margins: 18
                        clip: true
                        spacing: 4
                        model: controller ? controller.skillModel : null
                        delegate: Rectangle {
                            required property string skillId
                            required property string name
                            required property string description
                            required property string source
                            required property string path
                            required property string warning
                            width: ListView.view.width
                            height: 64
                            radius: 10
                            color: skillManagerMouse.containsMouse ? root.surfaceSoft : "transparent"
                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 12
                                anchors.rightMargin: 12
                                spacing: 12
                                Rectangle {
                                    Layout.preferredWidth: 32
                                    Layout.preferredHeight: 32
                                    radius: 8
                                    color: root.accentSoft
                                    Text { anchors.centerIn: parent; text: "$"; color: root.accent; font.pixelSize: 13; font.weight: Font.Bold }
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 2
                                    Text { text: skillId; color: root.textPrimary; font.pixelSize: 11; font.weight: Font.DemiBold }
                                    Text { Layout.fillWidth: true; text: description; color: root.textMuted; font.pixelSize: 9; elide: Text.ElideRight }
                                }
                                Text { text: "调用  ↗"; color: root.accent; font.pixelSize: 9; font.weight: Font.DemiBold }
                            }
                            MouseArea {
                                id: skillManagerMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    promptInput.text = "$" + skillId + " "
                                    promptInput.cursorPosition = promptInput.length
                                    skillsDialog.close()
                                    promptInput.forceActiveFocus()
                                }
                            }
                        }
                        footer: Text {
                            width: parent ? parent.width : 0
                            topPadding: 12
                            text: controller && controller.skillCount === 0
                                  ? "当前项目还没有 Skill，可在下一页创建或导入。" : "附带脚本不会自动执行，工具声明也不会授予权限。"
                            color: root.textMuted
                            font.pixelSize: 9
                            wrapMode: Text.Wrap
                        }
                    }
                }
                Item {
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 20
                        spacing: 9
                        TextField { id: newSkillName; Layout.fillWidth: true; placeholderText: "Skill 名称，例如 review-changes" }
                        TextField { id: newSkillDescription; Layout.fillWidth: true; placeholderText: "一句话说明用途" }
                        TextArea {
                            id: newSkillInstructions
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            placeholderText: "写下 Skill 指令；可使用 $ARGUMENTS 或 $1…$9"
                            wrapMode: TextEdit.Wrap
                            background: Rectangle { radius: 8; color: root.surfaceSoft; border.color: root.line }
                        }
                        TextField { id: newSkillTools; Layout.fillWidth: true; placeholderText: "声明工具，逗号分隔（可选，不会自动授权）" }
                        RowLayout {
                            Layout.fillWidth: true
                            QuietButton {
                                label: "创建 Skill"
                                prominent: true
                                enabled: newSkillName.text.trim().length > 0
                                         && newSkillInstructions.text.trim().length > 0
                                onClicked: {
                                    controller.createProjectSkill(newSkillName.text,
                                                                  newSkillDescription.text,
                                                                  newSkillInstructions.text,
                                                                  newSkillTools.text)
                                    newSkillName.clear()
                                    newSkillDescription.clear()
                                    newSkillInstructions.clear()
                                    newSkillTools.clear()
                                    skillTabs.currentIndex = 0
                                }
                            }
                            QuietButton { label: "导入本地文件夹"; onClicked: skillFolderDialog.open() }
                            Item { Layout.fillWidth: true }
                        }
                    }
                }
                Item {
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 20
                        spacing: 10
                        Text {
                            Layout.fillWidth: true
                            text: "通过本机 gh 登录下载公开或私密仓库。只安装指定目录，不运行仓库代码。"
                            color: root.textSecondary
                            font.pixelSize: 10
                            wrapMode: Text.Wrap
                        }
                        TextField { id: githubSkillRepo; Layout.fillWidth: true; placeholderText: "仓库：owner/repo 或 GitHub URL" }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            TextField { id: githubSkillRef; Layout.preferredWidth: 170; placeholderText: "分支 / Tag（可选）" }
                            TextField { id: githubSkillPath; Layout.fillWidth: true; placeholderText: "Skill 目录，例如 skills/review" }
                        }
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 86
                            radius: 9
                            color: root.surfaceSoft
                            Text {
                                anchors.fill: parent
                                anchors.margins: 12
                                text: "安装前校验\n· 必须存在有效 SKILL.md\n· 拒绝符号链接、路径逃逸、超大文件与同名覆盖"
                                color: root.textMuted
                                font.pixelSize: 9
                                lineHeight: 1.35
                            }
                        }
                        QuietButton {
                            label: "从 GitHub 安装"
                            prominent: true
                            enabled: githubSkillRepo.text.trim().length > 0
                                     && githubSkillPath.text.trim().length > 0
                            onClicked: controller.installGitHubSkill(githubSkillRepo.text,
                                                                     githubSkillRef.text,
                                                                     githubSkillPath.text)
                        }
                        Item { Layout.fillHeight: true }
                    }
                }
            }
            Hairline { Layout.fillWidth: true }
            RowLayout {
                Layout.fillWidth: true
                Layout.margins: 16
                Item { Layout.fillWidth: true }
                QuietButton { label: "完成"; prominent: true; onClicked: skillsDialog.close() }
            }
        }
    }

    Dialog {
        id: connectionsDialog
        objectName: "connectionsDialog"
        anchors.centerIn: parent
        width: Math.min(660, root.width - 80)
        modal: true
        closePolicy: Popup.CloseOnEscape
        padding: 0
        background: Rectangle {
            radius: 16
            color: root.surface
            border.color: root.lineStrong
            border.width: 1
        }
        contentItem: ColumnLayout {
            spacing: 0
            ColumnLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                Layout.topMargin: 20
                Layout.bottomMargin: 18
                spacing: 5
                Text { text: "工具与连接"; color: root.textPrimary; font.pixelSize: 18; font.weight: Font.DemiBold }
                Text {
                    text: controller ? controller.builtinToolCount + " 个内置工具已就绪  ·  "
                                       + controller.mcpServerCount + " 个 MCP 已启用" : ""
                    color: root.textMuted
                    font.pixelSize: 10
                }
            }
            Hairline { Layout.fillWidth: true }
            ScrollView {
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(520, root.height - 220)
                clip: true
                ColumnLayout {
                    width: connectionsDialog.width - 48
                    spacing: 8
                    Text {
                        Layout.topMargin: 20
                        text: "BRAVE SEARCH MCP"
                        color: root.textMuted
                        font.pixelSize: 9
                        font.letterSpacing: 1.0
                    }
                    Text {
                        Layout.fillWidth: true
                        text: "通过受控 MCP 提供网页、新闻与 LLM Context 搜索。Key 仅从环境或系统钥匙串读取；需要本机已安装 Node.js / npx。"
                        color: root.textSecondary
                        font.pixelSize: 10
                        wrapMode: Text.Wrap
                    }
                    TextField {
                        id: braveKeyInput
                        Layout.fillWidth: true
                        Layout.topMargin: 6
                        placeholderText: controller && controller.braveKeyPresent
                                         ? "系统钥匙串中已有 BRAVE_API_KEY" : "输入 Brave API Key"
                        echoMode: TextInput.Password
                        font.pixelSize: 11
                        background: Rectangle {
                            radius: 8
                            color: root.surfaceSoft
                            border.color: braveKeyInput.activeFocus ? root.accent : root.line
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        QuietButton {
                            label: controller && controller.braveConfigured ? "更新配置" : "启用 Brave"
                            prominent: true
                            onClicked: {
                                controller.configureBraveSearch(braveKeyInput.text)
                                braveKeyInput.clear()
                            }
                        }
                        QuietButton {
                            label: "测试连接"
                            enabled: controller ? controller.mcpServerCount > 0 : false
                            onClicked: controller.testMcpConnections()
                        }
                        QuietButton {
                            label: "停用"
                            enabled: controller ? controller.braveConfigured : false
                            onClicked: controller.disableBraveSearch()
                        }
                        Item { Layout.fillWidth: true }
                        Text {
                            text: controller ? controller.mcpStatus : ""
                            color: root.textMuted
                            font.pixelSize: 9
                            elide: Text.ElideRight
                        }
                    }
                    Hairline { Layout.fillWidth: true; Layout.topMargin: 16; Layout.bottomMargin: 12 }
                    Text {
                        text: "自定义 STDIO MCP"
                        color: root.textPrimary
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                    }
                    Text {
                        Layout.fillWidth: true
                        text: "自定义服务默认按高风险工具处理；这里只保存环境变量名称，不保存值。"
                        color: root.textMuted
                        font.pixelSize: 9
                        wrapMode: Text.Wrap
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        TextField {
                            id: customMcpName
                            Layout.preferredWidth: 150
                            placeholderText: "名称"
                            font.pixelSize: 10
                        }
                        TextField {
                            id: customMcpCommand
                            Layout.fillWidth: true
                            placeholderText: "命令，例如 uvx my-mcp-server"
                            font.pixelSize: 10
                        }
                    }
                    TextField {
                        id: customMcpEnv
                        Layout.fillWidth: true
                        placeholderText: "允许传入的环境变量名，逗号分隔（可选）"
                        font.pixelSize: 10
                    }
                    QuietButton {
                        label: "保存自定义 MCP"
                        enabled: customMcpName.text.trim().length > 0
                                 && customMcpCommand.text.trim().length > 0
                        onClicked: {
                            controller.configureCustomMcp(customMcpName.text,
                                                          customMcpCommand.text,
                                                          customMcpEnv.text)
                            customMcpName.clear()
                            customMcpCommand.clear()
                            customMcpEnv.clear()
                        }
                    }
                    Item { Layout.preferredHeight: 18 }
                }
            }
            Hairline { Layout.fillWidth: true }
            RowLayout {
                Layout.fillWidth: true
                Layout.margins: 16
                Item { Layout.fillWidth: true }
                QuietButton { label: "完成"; prominent: true; onClicked: connectionsDialog.close() }
            }
        }
    }

    Dialog {
        id: githubDialog
        objectName: "githubDialog"
        anchors.centerIn: parent
        width: Math.min(760, root.width - 80)
        modal: true
        closePolicy: Popup.CloseOnEscape
        padding: 0
        background: Rectangle { radius: 16; color: root.surface; border.color: root.lineStrong; border.width: 1 }
        contentItem: ColumnLayout {
            spacing: 0
            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                Layout.topMargin: 20
                Layout.bottomMargin: 16
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    Text { text: "GitHub"; color: root.textPrimary; font.pixelSize: 18; font.weight: Font.DemiBold }
                    Text {
                        text: controller
                              ? (controller.githubConnected
                                 ? controller.githubRepository + "  ·  " + controller.githubVisibility
                                 : controller.githubStatus)
                              : ""
                        color: root.textMuted
                        font.pixelSize: 10
                    }
                }
                MetaPill {
                    visible: controller ? controller.githubConnected : false
                    label: controller ? controller.githubAccount + "  /  " + controller.githubBranch : ""
                    dotColor: controller && controller.githubDirty ? root.danger : root.success
                }
                QuietButton { label: "刷新"; glyph: "↻"; onClicked: controller.refreshGitHub() }
            }
            TabBar {
                id: githubTabs
                Layout.fillWidth: true
                background: Rectangle { color: "transparent" }
                SegmentTab { text: "概览" }
                SegmentTab { text: "Pull Requests" }
                SegmentTab { text: "Issues" }
                SegmentTab { text: "Actions" }
            }
            Hairline { Layout.fillWidth: true }
            StackLayout {
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(500, root.height - 270)
                currentIndex: githubTabs.currentIndex
                Item {
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 24
                        spacing: 12
                        Text { text: "仓库同步"; color: root.textPrimary; font.pixelSize: 13; font.weight: Font.DemiBold }
                        Text {
                            Layout.fillWidth: true
                            text: controller && controller.githubConnected
                                  ? "分支 " + controller.githubBranch
                                    + (controller.githubDirty ? "  ·  有未提交变更" : "  ·  工作区干净")
                                  : "需要本机 gh 登录，并为当前项目配置 GitHub origin。"
                            color: controller && controller.githubDirty ? root.danger : root.textSecondary
                            font.pixelSize: 10
                        }
                        RowLayout {
                            spacing: 8
                            QuietButton { label: "Fetch"; onClicked: controller.syncGitHub("fetch") }
                            QuietButton {
                                label: "Pull（仅快进）"
                                enabled: controller ? controller.githubConnected && !controller.githubDirty : false
                                onClicked: {
                                    root.githubPendingSync = "pull_ff"
                                    githubSyncDialog.open()
                                }
                            }
                            QuietButton {
                                label: "Push 当前分支"
                                prominent: true
                                enabled: controller ? controller.githubConnected : false
                                onClicked: {
                                    root.githubPendingSync = "push"
                                    githubSyncDialog.open()
                                }
                            }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            TextField {
                                id: githubBranchName
                                Layout.fillWidth: true
                                placeholderText: "新分支名称，例如 codex/search-tools"
                            }
                            QuietButton {
                                label: "创建并切换"
                                enabled: githubBranchName.text.trim().length > 0
                                         && controller && !controller.githubDirty
                                onClicked: {
                                    controller.createGitHubBranch(githubBranchName.text)
                                    githubBranchName.clear()
                                }
                            }
                        }
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 100
                            radius: 10
                            color: root.surfaceSoft
                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 14
                                Text { text: "安全边界"; color: root.textPrimary; font.pixelSize: 10; font.weight: Font.DemiBold }
                                Text {
                                    Layout.fillWidth: true
                                    text: "只操作当前 workspace 的 origin；禁止 force push、远程删除、自动合并和仓库权限修改。模型发起的所有写操作仍需审批。"
                                    color: root.textMuted
                                    font.pixelSize: 9
                                    wrapMode: Text.Wrap
                                }
                            }
                        }
                        Item { Layout.fillHeight: true }
                    }
                }
                Item {
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 18
                        spacing: 8
                        ListView {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 190
                            clip: true
                            model: controller ? controller.githubPullRequestModel : null
                            delegate: Rectangle {
                                required property int number
                                required property string title
                                required property string detail
                                width: ListView.view.width
                                height: 54
                                color: "transparent"
                                ColumnLayout {
                                    anchors.fill: parent
                                    Text { Layout.fillWidth: true; text: "#" + number + "  " + title; color: root.textPrimary; font.pixelSize: 10; font.weight: Font.DemiBold; elide: Text.ElideRight }
                                    Text { text: detail; color: root.textMuted; font.pixelSize: 8 }
                                }
                                Hairline { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom }
                            }
                        }
                        Hairline { Layout.fillWidth: true }
                        TextField { id: prTitle; Layout.fillWidth: true; placeholderText: "新 Pull Request 标题" }
                        RowLayout {
                            Layout.fillWidth: true
                            TextField { id: prBase; Layout.preferredWidth: 150; text: "main"; placeholderText: "目标分支" }
                            CheckBox { id: prDraft; text: "草稿"; font.pixelSize: 10 }
                            Item { Layout.fillWidth: true }
                            QuietButton { label: "创建 PR"; prominent: true; enabled: prTitle.text.trim().length > 0; onClicked: controller.createGitHubPullRequest(prTitle.text, prBody.text, prBase.text, prDraft.checked) }
                        }
                        TextArea { id: prBody; Layout.fillWidth: true; Layout.fillHeight: true; placeholderText: "说明（可选）"; wrapMode: TextEdit.Wrap; background: Rectangle { radius: 8; color: root.surfaceSoft; border.color: root.line } }
                    }
                }
                Item {
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 18
                        spacing: 8
                        ListView {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 210
                            clip: true
                            model: controller ? controller.githubIssueModel : null
                            delegate: Rectangle {
                                required property int number
                                required property string title
                                required property string detail
                                width: ListView.view.width
                                height: 54
                                color: "transparent"
                                ColumnLayout {
                                    anchors.fill: parent
                                    Text {
                                        Layout.fillWidth: true
                                        text: "#" + number + "  " + title
                                        color: root.textPrimary
                                        font.pixelSize: 10
                                        font.weight: Font.DemiBold
                                        elide: Text.ElideRight
                                    }
                                    Text { text: detail; color: root.textMuted; font.pixelSize: 8 }
                                }
                                Hairline { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom }
                            }
                        }
                        TextField { id: issueTitle; Layout.fillWidth: true; placeholderText: "新 Issue 标题" }
                        TextArea { id: issueBody; Layout.fillWidth: true; Layout.fillHeight: true; placeholderText: "问题说明（可选）"; wrapMode: TextEdit.Wrap; background: Rectangle { radius: 8; color: root.surfaceSoft; border.color: root.line } }
                        QuietButton { label: "创建 Issue"; prominent: true; enabled: issueTitle.text.trim().length > 0; onClicked: controller.createGitHubIssue(issueTitle.text, issueBody.text) }
                    }
                }
                Item {
                    ListView {
                        anchors.fill: parent
                        anchors.margins: 18
                        clip: true
                        spacing: 2
                        model: controller ? controller.githubActionModel : null
                        delegate: Rectangle {
                            required property int runId
                            required property string title
                            required property string detail
                            required property string status
                            width: ListView.view.width
                            height: 62
                            color: "transparent"
                            RowLayout {
                                anchors.fill: parent
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Text { Layout.fillWidth: true; text: title; color: root.textPrimary; font.pixelSize: 10; font.weight: Font.DemiBold; elide: Text.ElideRight }
                                    Text { text: detail + "  ·  " + status; color: status === "success" ? root.success : root.textMuted; font.pixelSize: 8 }
                                }
                                QuietButton { label: "重跑失败项"; enabled: status === "failure"; onClicked: controller.rerunGitHubAction(runId) }
                            }
                            Hairline { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom }
                        }
                    }
                }
            }
            Hairline { Layout.fillWidth: true }
            RowLayout {
                Layout.fillWidth: true
                Layout.margins: 16
                Text { Layout.fillWidth: true; text: controller ? controller.githubStatus : ""; color: root.textMuted; font.pixelSize: 9; elide: Text.ElideRight }
                QuietButton { label: "完成"; prominent: true; onClicked: githubDialog.close() }
            }
        }
    }

    Dialog {
        id: githubSyncDialog
        anchors.centerIn: parent
        width: Math.min(430, root.width - 80)
        modal: true
        closePolicy: Popup.NoAutoClose
        title: "确认 GitHub 同步"
        standardButtons: Dialog.NoButton
        contentItem: ColumnLayout {
            spacing: 14
            Text {
                Layout.fillWidth: true
                text: root.githubPendingSync === "push"
                      ? "将当前分支非强制推送到 origin。确定继续？"
                      : "将使用 --ff-only 拉取当前分支，不会自动创建合并提交。确定继续？"
                color: root.textSecondary
                font.pixelSize: 11
                wrapMode: Text.Wrap
            }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                QuietButton { label: "取消"; onClicked: githubSyncDialog.close() }
                QuietButton {
                    label: "确认执行"
                    prominent: true
                    onClicked: {
                        controller.syncGitHub(root.githubPendingSync)
                        githubSyncDialog.close()
                    }
                }
            }
        }
    }

    Dialog {
        id: approvalDialog
        anchors.centerIn: parent
        width: Math.min(560, root.width - 80)
        modal: true
        closePolicy: Popup.NoAutoClose
        padding: 0
        background: Rectangle {
            radius: 16
            color: root.surface
            border.color: root.lineStrong
            border.width: 1
        }
        contentItem: ColumnLayout {
            spacing: 0
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 84
                color: "transparent"
                Column {
                    anchors.left: parent.left
                    anchors.leftMargin: 24
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 5
                    Text { id: approvalTitle; color: root.textPrimary; font.pixelSize: 17; font.weight: Font.DemiBold }
                    Text { id: approvalRisk; color: root.accent; font.pixelSize: 10 }
                }
            }
            Hairline { Layout.fillWidth: true }
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 190
                Layout.margins: 20
                radius: 10
                color: "#F7F8FA"
                border.color: root.line
                ScrollView {
                    anchors.fill: parent
                    anchors.margins: 14
                    TextArea {
                        id: approvalDetails
                        readOnly: true
                        color: root.textSecondary
                        font.family: "Menlo"
                        font.pixelSize: 11
                        wrapMode: TextEdit.WrapAnywhere
                        background: Item { }
                    }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 20
                Layout.rightMargin: 20
                Layout.bottomMargin: 20
                spacing: 10
                Item { Layout.fillWidth: true }
                QuietButton {
                    label: "拒绝"
                    onClicked: {
                        controller.resolveApproval(root.approvalId, "deny")
                        approvalDialog.close()
                    }
                }
                QuietButton {
                    label: "取消运行"
                    onClicked: {
                        controller.resolveApproval(root.approvalId, "cancel_run")
                        approvalDialog.close()
                    }
                }
                QuietButton {
                    label: "本会话允许"
                    onClicked: {
                        controller.resolveApproval(root.approvalId, "allow_session")
                        approvalDialog.close()
                    }
                }
                QuietButton {
                    label: "允许一次"
                    prominent: true
                    onClicked: {
                        controller.resolveApproval(root.approvalId, "allow_once")
                        approvalDialog.close()
                    }
                }
            }
        }
    }

    Rectangle {
        id: toast
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 24
        width: Math.min(toastText.implicitWidth + 42, root.width - 80)
        height: 44
        radius: 11
        color: "#FFF0F0"
        border.color: "#E1B4B4"
        opacity: 0
        visible: opacity > 0
        z: 20
        Text {
            id: toastText
            anchors.centerIn: parent
            width: parent.width - 28
            color: root.danger
            font.pixelSize: 11
            elide: Text.ElideRight
            horizontalAlignment: Text.AlignHCenter
        }
        Behavior on opacity { NumberAnimation { duration: 180 } }
        Timer {
            id: toastTimer
            interval: 4200
            onTriggered: toast.opacity = 0
        }
    }
}
