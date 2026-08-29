import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

ApplicationWindow {
    id: root
    width: 1440
    height: 900
    minimumWidth: 1040
    minimumHeight: 680
    visible: true
    title: (controller ? controller.currentSessionTitle : "YF-Harness") + " — YF-Harness"
    color: "#0B0E11"

    readonly property color canvas: "#0B0E11"
    readonly property color surface: "#11161B"
    readonly property color raised: "#171D23"
    readonly property color line: "#252C33"
    readonly property color textPrimary: "#F3EEE5"
    readonly property color textSecondary: "#99A3AC"
    readonly property color textMuted: "#67727D"
    readonly property color accent: "#D8A25E"
    readonly property color success: "#77B88D"
    property string approvalId: ""
    property int inspectorTab: 0

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
        signal clicked()
        implicitWidth: buttonContent.implicitWidth + 28
        implicitHeight: 38
        radius: 9
        color: prominent ? root.accent : (buttonMouse.containsMouse ? "#20272E" : "transparent")
        border.width: prominent ? 0 : 1
        border.color: root.line
        opacity: enabled ? 1 : 0.42
        Row {
            id: buttonContent
            anchors.centerIn: parent
            spacing: 8
            Text {
                visible: quietButton.glyph.length > 0
                text: quietButton.glyph
                color: quietButton.prominent ? root.canvas : root.textSecondary
                font.pixelSize: 14
                font.weight: Font.DemiBold
            }
            Text {
                text: quietButton.label
                color: quietButton.prominent ? root.canvas : root.textPrimary
                font.pixelSize: 13
                font.weight: Font.DemiBold
            }
        }
        MouseArea {
            id: buttonMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            enabled: quietButton.enabled
            onClicked: quietButton.clicked()
        }
        Behavior on color { ColorAnimation { duration: 120 } }
        scale: buttonMouse.pressed ? 0.97 : 1
        Behavior on scale { NumberAnimation { duration: 90 } }
    }

    component ControlSelect: ComboBox {
        id: select
        implicitHeight: 38
        font.pixelSize: 12
        leftPadding: 12
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
            radius: 8
            color: select.hovered ? "#1B2229" : root.raised
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
                radius: 10
                color: "#1B2229"
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
                color: highlighted ? "#2A323A" : "transparent"
            }
            highlighted: select.highlightedIndex === index
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
        onActivated: controller.cancelRun()
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
            approvalDetails.text = JSON.stringify(request.tool_call.arguments, null, 2)
            approvalDialog.open()
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            id: sidebar
            Layout.preferredWidth: root.width < 1180 ? 238 : 276
            Layout.fillHeight: true
            color: root.surface
            border.width: 0

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 18
                spacing: 0

                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 52
                    spacing: 12
                    Rectangle {
                        width: 34
                        height: 34
                        radius: 10
                        color: root.accent
                        Text {
                            anchors.centerIn: parent
                            text: "YF"
                            color: root.canvas
                            font.pixelSize: 13
                            font.weight: Font.Black
                        }
                    }
                    Column {
                        id: emptyState
                        Layout.fillWidth: true
                        spacing: 1
                        Text {
                            text: "YF-Harness"
                            color: root.textPrimary
                            font.pixelSize: 15
                            font.weight: Font.DemiBold
                        }
                        Text {
                            text: "LOCAL AGENT WORKSPACE"
                            color: root.textMuted
                            font.pixelSize: 8
                            font.letterSpacing: 1.2
                        }
                    }
                }

                QuietButton {
                    Layout.fillWidth: true
                    Layout.topMargin: 18
                    label: "新建任务"
                    glyph: "+"
                    prominent: true
                    onClicked: controller.newSession()
                }

                TextField {
                    id: sessionSearch
                    Layout.fillWidth: true
                    Layout.topMargin: 18
                    Layout.preferredHeight: 38
                    placeholderText: "搜索会话"
                    placeholderTextColor: root.textMuted
                    color: root.textPrimary
                    font.pixelSize: 12
                    leftPadding: 34
                    background: Rectangle {
                        radius: 9
                        color: "#0E1216"
                        border.width: 1
                        border.color: sessionSearch.activeFocus ? root.accent : root.line
                    }
                    Text {
                        anchors.left: parent.left
                        anchors.leftMargin: 12
                        anchors.verticalCenter: parent.verticalCenter
                        text: "⌕"
                        color: root.textMuted
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
                    Layout.topMargin: 22
                    Layout.bottomMargin: 8
                    Text {
                        text: "最近会话"
                        color: root.textSecondary
                        font.pixelSize: 10
                        font.weight: Font.DemiBold
                        font.letterSpacing: 0.8
                    }
                    Item { Layout.fillWidth: true }
                    Text {
                        text: sessionList.count
                        color: root.textMuted
                        font.pixelSize: 10
                    }
                }

                ListView {
                    id: sessionList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: 3
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
                        height: 62
                        radius: 9
                        color: controller && controller.currentSessionId === sessionId
                               ? "#20272D"
                               : (sessionMouse.containsMouse ? "#181E24" : "transparent")
                        Rectangle {
                            visible: controller ? controller.currentSessionId === sessionRow.sessionId : false
                            width: 3
                            height: 28
                            radius: 2
                            color: root.accent
                            anchors.left: parent.left
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Column {
                            anchors.left: parent.left
                            anchors.leftMargin: 13
                            anchors.right: parent.right
                            anchors.rightMargin: 10
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 5
                            Text {
                                width: parent.width
                                text: sessionRow.title
                                color: root.textPrimary
                                font.pixelSize: 12
                                font.weight: Font.Medium
                                elide: Text.ElideRight
                            }
                            Row {
                                width: parent.width
                                Text {
                                    width: parent.width - sessionTime.width - 8
                                    text: sessionRow.detail
                                    color: root.textMuted
                                    font.pixelSize: 9
                                    elide: Text.ElideRight
                                }
                                Text {
                                    id: sessionTime
                                    text: sessionRow.updated
                                    color: root.textMuted
                                    font.pixelSize: 9
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

                Hairline { Layout.fillWidth: true; Layout.topMargin: 12; Layout.bottomMargin: 14 }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 9
                    Rectangle {
                        width: 30
                        height: 30
                        radius: 15
                        color: "#243029"
                        Text {
                            anchors.centerIn: parent
                            text: "●"
                            color: root.success
                            font.pixelSize: 10
                        }
                    }
                    Column {
                        Layout.fillWidth: true
                        Text { text: "本地工作区"; color: root.textPrimary; font.pixelSize: 11 }
                        Text {
                            width: sidebar.width - 76
                            text: controller ? controller.workspacePath : ""
                            color: root.textMuted
                            font.pixelSize: 9
                            elide: Text.ElideMiddle
                        }
                    }
                }
                QuietButton {
                    Layout.fillWidth: true
                    Layout.topMargin: 10
                    label: "打开项目文件夹"
                    glyph: "⌁"
                    enabled: controller ? !controller.busy : false
                    onClicked: projectFolderDialog.open()
                }
            }
        }

        Hairline { Layout.fillHeight: true }

        Rectangle {
            id: workspace
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
                    Layout.rightMargin: 30
                    spacing: 14
                    Column {
                        Layout.fillWidth: true
                        spacing: 3
                        Text {
                            text: controller ? controller.currentSessionTitle : ""
                            color: root.textPrimary
                            font.pixelSize: 18
                            font.weight: Font.DemiBold
                            elide: Text.ElideRight
                        }
                        Row {
                            spacing: 7
                            Rectangle {
                                width: 7
                                height: 7
                                radius: 4
                                color: controller && controller.busy ? root.accent : root.success
                                anchors.verticalCenter: parent.verticalCenter
                                SequentialAnimation on opacity {
                                    running: controller ? controller.busy : false
                                    loops: Animation.Infinite
                                    NumberAnimation { to: 0.3; duration: 650 }
                                    NumberAnimation { to: 1; duration: 650 }
                                }
                            }
                            Text {
                                text: controller ? controller.statusText : ""
                                color: root.textMuted
                                font.pixelSize: 10
                            }
                        }
                    }
                    QuietButton {
                        label: "取消"
                        glyph: "×"
                        visible: controller ? controller.busy : false
                        onClicked: controller.cancelRun()
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
                        anchors.leftMargin: Math.max(34, (width - 860) / 2)
                        anchors.rightMargin: Math.max(34, (width - 860) / 2)
                        anchors.topMargin: 26
                        anchors.bottomMargin: 18
                        model: controller ? controller.messageModel : null
                        spacing: 24
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
                                spacing: 7

                                Row {
                                    anchors.right: messageDelegate.isUser ? parent.right : undefined
                                    spacing: 8
                                    Text {
                                        text: messageDelegate.speaker.toUpperCase()
                                        color: messageDelegate.isUser ? root.accent : root.textMuted
                                        font.pixelSize: 9
                                        font.weight: Font.DemiBold
                                        font.letterSpacing: 0.8
                                    }
                                    Text {
                                        text: messageDelegate.timestamp
                                        color: root.textMuted
                                        font.pixelSize: 9
                                    }
                                }

                                Rectangle {
                                    visible: !messageDelegate.isTool
                                    anchors.right: messageDelegate.isUser ? parent.right : undefined
                                    width: messageDelegate.isUser
                                           ? Math.min(messageText.implicitWidth + 32, parent.width * 0.78)
                                           : parent.width
                                    height: messageText.implicitHeight + (messageDelegate.isUser ? 24 : 6)
                                    radius: messageDelegate.isUser ? 14 : 0
                                    color: messageDelegate.isUser ? "#20272E" : "transparent"
                                    border.width: 0
                                    Rectangle {
                                        visible: !messageDelegate.isUser
                                        width: 3
                                        height: Math.max(28, parent.height - 4)
                                        radius: 2
                                        color: messageDelegate.pending ? root.accent : "#39434D"
                                    }
                                    Text {
                                        id: messageText
                                        anchors.left: parent.left
                                        anchors.leftMargin: messageDelegate.isUser ? 16 : 18
                                        anchors.right: parent.right
                                        anchors.rightMargin: messageDelegate.isUser ? 16 : 4
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: messageDelegate.content || (messageDelegate.pending ? "正在思考…" : "")
                                        color: root.textPrimary
                                        font.pixelSize: 14
                                        lineHeight: 1.42
                                        wrapMode: Text.Wrap
                                        textFormat: Text.MarkdownText
                                        onLinkActivated: link => Qt.openUrlExternally(link)
                                    }
                                }

                                Rectangle {
                                    visible: messageDelegate.isTool
                                    width: parent.width
                                    height: 42
                                    radius: 9
                                    color: "#10151A"
                                    border.color: root.line
                                    border.width: 1
                                    Row {
                                        anchors.fill: parent
                                        anchors.leftMargin: 13
                                        anchors.rightMargin: 13
                                        spacing: 10
                                        Text {
                                            text: messageDelegate.pending ? "◌" : "✓"
                                            color: messageDelegate.pending ? root.accent : root.success
                                            font.pixelSize: 13
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                        Text {
                                            text: messageDelegate.content
                                            color: root.textSecondary
                                            font.pixelSize: 11
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Column {
                        visible: conversation.count === 0
                        anchors.centerIn: parent
                        width: Math.min(520, parent.width - 80)
                        spacing: 16
                        opacity: 0
                        transform: Translate { id: emptyTranslate; y: 18 }
                        Rectangle {
                            anchors.horizontalCenter: parent.horizontalCenter
                            width: 72
                            height: 72
                            radius: 23
                            color: root.raised
                            border.color: "#2F3942"
                            border.width: 1
                            Text {
                                anchors.centerIn: parent
                                text: "YF"
                                color: root.accent
                                font.pixelSize: 22
                                font.weight: Font.Black
                            }
                        }
                        Text {
                            width: parent.width
                            text: "从一个清晰的任务开始"
                            color: root.textPrimary
                            font.pixelSize: 25
                            font.weight: Font.DemiBold
                            horizontalAlignment: Text.AlignHCenter
                        }
                        Text {
                            width: parent.width
                            text: "描述目标，YF-Harness 会在本地安全边界内规划、调用工具并保留完整运行记录。"
                            color: root.textSecondary
                            font.pixelSize: 13
                            lineHeight: 1.4
                            wrapMode: Text.Wrap
                            horizontalAlignment: Text.AlignHCenter
                        }
                        Row {
                            anchors.horizontalCenter: parent.horizontalCenter
                            spacing: 8
                            Repeater {
                                model: ["分析项目结构", "制定实施计划", "检查代码风险"]
                                Rectangle {
                                    required property string modelData
                                    width: suggestionLabel.implicitWidth + 24
                                    height: 34
                                    radius: 9
                                    color: suggestionMouse.containsMouse ? "#20272E" : root.surface
                                    border.color: root.line
                                    Text {
                                        id: suggestionLabel
                                        anchors.centerIn: parent
                                        text: modelData
                                        color: root.textSecondary
                                        font.pixelSize: 11
                                    }
                                    MouseArea {
                                        id: suggestionMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            promptInput.text = modelData
                                            promptInput.forceActiveFocus()
                                        }
                                    }
                                }
                            }
                        }
                        Component.onCompleted: emptyEntrance.start()
                        ParallelAnimation {
                            id: emptyEntrance
                            NumberAnimation { target: emptyState; property: "opacity"; to: 1; duration: 360; easing.type: Easing.OutCubic }
                            NumberAnimation { target: emptyTranslate; property: "y"; to: 0; duration: 420; easing.type: Easing.OutCubic }
                        }
                    }
                }

                Rectangle {
                    visible: controller ? controller.queueCount > 0 : false
                    Layout.fillWidth: true
                    Layout.leftMargin: Math.max(26, (workspace.width - 900) / 2)
                    Layout.rightMargin: Math.max(26, (workspace.width - 900) / 2)
                    Layout.preferredHeight: 42
                    radius: 10
                    color: "#151B20"
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
                    Layout.leftMargin: Math.max(26, (workspace.width - 900) / 2)
                    Layout.rightMargin: Math.max(26, (workspace.width - 900) / 2)
                    Layout.preferredHeight: visible ? Math.min(238, 48 + skillList.count * 54) : 0
                    radius: 13
                    color: "#171D23"
                    border.width: 1
                    border.color: "#3B3329"
                    clip: true

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 4
                        RowLayout {
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
                                       ? "#242B31" : "transparent"
                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 10
                                    anchors.rightMargin: 10
                                    spacing: 11
                                    Rectangle {
                                        Layout.preferredWidth: 58
                                        Layout.preferredHeight: 23
                                        radius: 6
                                        color: "#30291F"
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
                    Layout.fillWidth: true
                    Layout.leftMargin: Math.max(26, (workspace.width - 900) / 2)
                    Layout.rightMargin: Math.max(26, (workspace.width - 900) / 2)
                    Layout.bottomMargin: 22
                    Layout.preferredHeight: controller && controller.attachmentCount > 0 ? 172 : 142
                    radius: 15
                    color: root.surface
                    border.width: 1
                    border.color: promptInput.activeFocus ? "#4A3B2A" : root.line

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 7
                        TextArea {
                            id: promptInput
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            placeholderText: "描述你想完成的任务…"
                            placeholderTextColor: root.textMuted
                            color: root.textPrimary
                            selectionColor: root.accent
                            selectedTextColor: root.canvas
                            font.pixelSize: 14
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
                                color: "#1B2228"
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
                            Layout.fillWidth: true
                            QuietButton {
                                label: "图片"
                                glyph: "+"
                                onClicked: imageDialog.open()
                            }
                            Switch {
                                id: sendImageSwitch
                                text: "发送图片内容"
                                checked: false
                                font.pixelSize: 10
                                palette.text: root.textSecondary
                                ToolTip.visible: hovered
                                ToolTip.text: checked
                                              ? "所选图片将发送给远程模型"
                                              : "默认仅在本地记录，不上传图片内容"
                            }
                            Text {
                                text: "⌘ ↵ 发送"
                                color: root.textMuted
                                font.pixelSize: 9
                            }
                            Item { Layout.fillWidth: true }
                            QuietButton {
                                label: controller && controller.busy ? "排队" : "发送"
                                glyph: controller && controller.busy ? "+" : "↑"
                                prominent: true
                                enabled: controller ? promptInput.text.trim().length > 0 : false
                                onClicked: root.sendCurrentPrompt()
                            }
                        }
                    }
                    Behavior on border.color { ColorAnimation { duration: 150 } }
                }
            }
        }

        Hairline {
            Layout.fillHeight: true
        }

        Rectangle {
            id: inspector
            Layout.preferredWidth: root.width >= 1240 ? 284 : 240
            Layout.fillHeight: true
            color: root.surface
            clip: true

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 0
                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        text: "工作台"
                        color: root.textPrimary
                        font.pixelSize: 14
                        font.weight: Font.DemiBold
                    }
                    Item { Layout.fillWidth: true }
                    Text {
                        text: controller && controller.busy ? "● LIVE" : "LOCAL"
                        color: controller && controller.busy ? root.accent : root.textMuted
                        font.pixelSize: 9
                        font.letterSpacing: 0.8
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: 16
                    spacing: 2
                    Repeater {
                        model: ["运行", "上下文", "变更"]
                        Rectangle {
                            required property string modelData
                            required property int index
                            Layout.fillWidth: true
                            height: 34
                            radius: 8
                            color: root.inspectorTab === index ? "#242B31" : "transparent"
                            Text {
                                anchors.centerIn: parent
                                text: modelData
                                color: root.inspectorTab === index ? root.textPrimary : root.textMuted
                                font.pixelSize: 11
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
                    Layout.topMargin: 14
                    currentIndex: root.inspectorTab

                    ScrollView {
                        clip: true
                        contentWidth: availableWidth
                        ColumnLayout {
                            width: parent.width
                            spacing: 0
                            Text { text: "PROVIDER"; color: root.textMuted; font.pixelSize: 9; font.letterSpacing: 0.9 }
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
                            Text { Layout.topMargin: 17; text: "MODEL"; color: root.textMuted; font.pixelSize: 9; font.letterSpacing: 0.9 }
                            ControlSelect { id: modelSelect; Layout.fillWidth: true; Layout.topMargin: 7 }
                            Text { Layout.topMargin: 17; text: "WORKFLOW"; color: root.textMuted; font.pixelSize: 9; font.letterSpacing: 0.9 }
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
                            Text { Layout.topMargin: 17; text: "MODE"; color: root.textMuted; font.pixelSize: 9; font.letterSpacing: 0.9 }
                            ControlSelect {
                                id: modeSelect
                                Layout.fillWidth: true
                                Layout.topMargin: 7
                                model: ["agent", "chat", "plan", "review"]
                                currentIndex: 0
                            }
                            Text { Layout.topMargin: 17; text: "PERMISSIONS"; color: root.textMuted; font.pixelSize: 9; font.letterSpacing: 0.9 }
                            ControlSelect {
                                id: permissionSelect
                                Layout.fillWidth: true
                                Layout.topMargin: 7
                                model: ["safe_auto", "always_ask", "deny_writes"]
                                currentIndex: 0
                            }

                            Rectangle {
                                visible: controller ? controller.hasExecutablePlan : false
                                Layout.fillWidth: true
                                Layout.topMargin: 20
                                implicitHeight: planColumn.implicitHeight + 24
                                radius: 11
                                color: "#191A18"
                                border.color: "#403523"
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
                                        color: "#0D1114"
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
                    text: "YF-Harness 0.6 · Local first"
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
            Behavior on Layout.preferredWidth { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
        }
    }

    FileDialog {
        id: imageDialog
        title: "选择项目内的图片"
        nameFilters: ["Images (*.png *.jpg *.jpeg *.gif *.webp)"]
        onAccepted: controller.addImage(selectedFile.toString(), sendImageSwitch.checked)
    }

    FolderDialog {
        id: projectFolderDialog
        title: "选择 YF-Harness 项目文件夹"
        onAccepted: controller.setWorkspace(selectedFolder.toString())
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
            color: "#171D23"
            border.color: "#3A424A"
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
                color: "#0E1216"
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
                        controller.resolveApproval(root.approvalId, false)
                        approvalDialog.close()
                    }
                }
                QuietButton {
                    label: "允许一次"
                    prominent: true
                    onClicked: {
                        controller.resolveApproval(root.approvalId, true)
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
        color: "#2B2020"
        border.color: "#664242"
        opacity: 0
        visible: opacity > 0
        z: 20
        Text {
            id: toastText
            anchors.centerIn: parent
            width: parent.width - 28
            color: "#F0C8C3"
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
