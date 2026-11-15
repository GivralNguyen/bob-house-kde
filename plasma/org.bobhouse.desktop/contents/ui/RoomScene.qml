pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import "Data.js" as Data
import "Rover.js" as Rover

FocusScope {
    id: scene
    objectName: "bobRoomScene"
    property string assetRoot: ""
    property string roomId: "study"
    property bool animations: true
    property bool showLabels: false
    property bool launchEnabled: true
    property bool companionOpen: false
    property var roomList: Data.rooms.rooms || []
    readonly property var currentRoom: roomById(roomId)
    readonly property bool pictureReady: background.status === Image.Ready
    property string speech: "Welcome home! Click an object to use it, or a door to visit another room."
    property int selectedIndex: -1
    property int poseId: 201
    property var actor: Rover.create(Data.timeline)
    property real clockTime: Date.now()
    property real animationTime: Date.now()
    signal roomRequested(string id)
    signal labelsRequested(bool show)
    signal animationsRequested(bool animate)
    signal actionRequested(string url)

    function asset(path) {
        return assetRoot.replace(/\/+$/, "") + "/" + path.replace(/^\/+/, "");
    }
    function roomById(id) {
        for (let i = 0; i < roomList.length; i++) {
            if (String(roomList[i].id) === String(id)) return roomList[i];
        }
        return roomList.length ? roomList[0] : {id: "", name: "Bob House KDE", width: 1600, height: 1200, hotspots: []};
    }
    function goToRoom(id) {
        if (!roomList.some(room => String(room.id) === String(id))) return;
        closeCompanion();
        selectedIndex = -1;
        roomRequested(String(id));
        speech = "Welcome to the " + roomById(id).name + ". Make yourself at home!";
        Rover.play(actor, "greeting", Date.now());
        roomMenu.close();
    }
    function showRoomChooser() {
        closeCompanion();
        roomMenu.open();
    }
    function showOptions() {
        closeCompanion();
        optionsMenu.open();
    }
    function showCompanion() {
        roomMenu.close();
        optionsMenu.close();
        selectedIndex = -1;
        companionOpen = true;
        Rover.play(actor, "ask", Date.now());
        programsChoice.forceActiveFocus(Qt.OtherFocusReason);
    }
    function closeCompanion() {
        if (!companionOpen) return;
        companionOpen = false;
        scene.forceActiveFocus();
    }
    function runCompanionCommand(command) {
        if (["programs", "rooms", "notes", "calendar", "clock", "options", "trick"].indexOf(command) === -1) return;
        closeCompanion();
        if (command === "rooms") showRoomChooser();
        else if (command === "options") showOptions();
        else if (command === "trick") doTrick();
        else {
            const messages = {
                programs: "Let's find the app or folder you want to open.",
                notes: "Here's your notepad. Remember to save your note!",
                calendar: "Let's take a look at your calendar.",
                clock: "Here's your timer. I'll be right here!"
            };
            speech = messages[command];
            Rover.play(actor, command === "notes" ? "writing" : "acknowledge", Date.now());
            openAction(command, false);
        }
    }
    function isActionAllowed(action, configure, objectId) {
        if (objectId !== undefined && objectId !== null) {
            return typeof objectId === "string" && (currentRoom.hotspots || []).some(
                hotspot => hotspot.id === objectId && hotspot.action === action);
        }
        if (configure) return false;
        if (!configure && ["settings", "help", "rover", "programs", "notes", "calendar", "clock"].indexOf(action) !== -1) return true;
        return (currentRoom.hotspots || []).some(hotspot => hotspot.action === action);
    }
    function openAction(action, configure, objectId) {
        if (!isActionAllowed(action, configure, objectId)) return;
        const verb = configure ? "configure" : "open";
        let url = "bobhouse://" + verb + "/" + encodeURIComponent(action)
                  + "?room=" + encodeURIComponent(String(currentRoom.id));
        if (objectId !== undefined && objectId !== null) url += "&object=" + encodeURIComponent(objectId);
        actionRequested(url);
        if (launchEnabled && !Qt.openUrlExternally(url)) {
            speech = "I couldn't open that. The Bob House KDE action helper needs to be registered.";
            Rover.play(actor, "error", Date.now());
        }
    }
    function useHotspot(hotspot, configure) {
        closeCompanion();
        if (hotspot.room !== undefined) {
            goToRoom(hotspot.room);
        } else if (hotspot.action) {
            speech = configure ? "Let's choose what " + hotspot.label + " opens." : "Opening " + hotspot.label + ". I'll be right here!";
            Rover.play(actor, hotspot.action === "letter" ? "mail" : "thinking", Date.now());
            openAction(hotspot.action, configure, hotspot.id);
        }
    }
    function doTrick() {
        const tricks = ["clicked", "roll", "laugh", "stretch", "fetch"];
        Rover.play(actor, tricks[Math.floor(Math.random() * tricks.length)], Date.now());
        speech = "Shift-click any object to choose its app or folder. Right-click for your usual desktop menu.";
    }
    function selectNext(backward) {
        const count = (currentRoom.hotspots || []).length;
        if (!count) return;
        selectedIndex = (selectedIndex + (backward ? count - 1 : 1)) % count;
        speech = currentRoom.hotspots[selectedIndex].label;
    }
    onRoomIdChanged: {
        closeCompanion();
        selectedIndex = -1;
    }
    onAnimationsChanged: {
        if (!actor) return;
        if (!animations) poseId = Rover.frame(actor, Date.now(), false);
        else Rover.play(actor, "idle", Date.now());
    }
    Component.onCompleted: Rover.play(actor, "greeting", Date.now())

    Keys.onPressed: event => {
        if (companionOpen) {
            if (event.key === Qt.Key_Escape) {
                closeCompanion();
                event.accepted = true;
            }
            return;
        }
        if (event.key === Qt.Key_F2) {
            showCompanion();
        } else if (event.key === Qt.Key_F1) {
            labelsRequested(!showLabels);
        } else if (event.key === Qt.Key_Tab || event.key === Qt.Key_Backtab) {
            selectNext(event.key === Qt.Key_Backtab || (event.modifiers & Qt.ShiftModifier));
        } else if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Space) && selectedIndex >= 0) {
            useHotspot(currentRoom.hotspots[selectedIndex], Boolean(event.modifiers & Qt.ShiftModifier));
        } else {
            return;
        }
        event.accepted = true;
    }

    Rectangle { anchors.fill: parent; color: "#20130e" }

    MouseArea {
        anchors.fill: parent
        visible: scene.companionOpen
        acceptedButtons: Qt.LeftButton
        onClicked: scene.closeCompanion()
    }

    Item {
        id: roomCanvas
        objectName: "roomCanvas"
        width: currentRoom.width || 1600
        height: currentRoom.height || 1200
        x: (scene.width - width) / 2
        y: (scene.height - height) / 2
        scale: Math.min(scene.width / width, scene.height / height)

        Image {
            id: background
            objectName: "roomBackground"
            anchors.fill: parent
            source: currentRoom.image ? scene.asset(currentRoom.animatedImage || currentRoom.image) : ""
            smooth: false
            cache: true
            asynchronous: true
            retainWhileLoading: true
        }

        Item {
            id: pendulumLayer
            readonly property var mechanism: scene.currentRoom.pendulum || null
            visible: Boolean(mechanism)
            x: mechanism ? mechanism.rect[0] : 0
            y: mechanism ? mechanism.rect[1] : 0
            width: mechanism ? mechanism.rect[2] : 0
            height: mechanism ? mechanism.rect[3] : 0
            z: 0.2
            Image {
                anchors.fill: parent
                source: pendulumLayer.mechanism ? scene.asset(pendulumLayer.mechanism.image) : ""
                smooth: false
                cache: true
                transform: Rotation {
                    origin.x: pendulumLayer.mechanism ? pendulumLayer.mechanism.pivot[0] : 0
                    origin.y: pendulumLayer.mechanism ? pendulumLayer.mechanism.pivot[1] : 0
                    angle: scene.animations && pendulumLayer.mechanism
                        ? Math.sin(scene.animationTime * Math.PI * 2 / (1000 * (pendulumLayer.mechanism.period || 2.4)))
                          * (pendulumLayer.mechanism.angle || 4)
                        : 0
                }
            }
            Image {
                anchors.fill: parent
                source: pendulumLayer.mechanism ? scene.asset(pendulumLayer.mechanism.foreground) : ""
                smooth: false
                cache: true
            }
        }

        Repeater {
            model: scene.currentRoom.calendars || (scene.currentRoom.calendar ? [scene.currentRoom.calendar] : [])
            Text {
                required property var modelData
                x: modelData.rect[0]
                y: modelData.rect[1]
                width: modelData.rect[2]
                height: modelData.rect[3]
                text: Qt.formatDateTime(new Date(scene.clockTime), "MMM d")
                font.family: "Times New Roman"
                font.pixelSize: 29
                minimumPixelSize: 14
                fontSizeMode: Text.Fit
                color: "#cf0b18"
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                z: 0.5
            }
        }

        Canvas {
            id: clockHands
            anchors.fill: parent
            visible: Boolean(scene.currentRoom.clock && scene.currentRoom.clock.kind === "analog")
            z: 0.5
            onPaint: {
                const context = getContext("2d");
                context.clearRect(0, 0, width, height);
                const face = scene.currentRoom.clock;
                if (!face || face.kind !== "analog") return;
                const date = new Date(scene.clockTime);
                const radius = Math.min(face.rx, face.ry);
                const angles = [
                    [(date.getHours() % 12 + date.getMinutes() / 60) * Math.PI / 6, radius * 0.57, 4, "#302005"],
                    [(date.getMinutes() + date.getSeconds() / 60) * Math.PI / 30, radius * 0.79, 3, "#302005"],
                    [date.getSeconds() * Math.PI / 30, radius * 0.84, 1.5, "#a13210"]
                ];
                for (let i = 0; i < angles.length; i++) {
                    const hand = angles[i];
                    context.beginPath();
                    context.strokeStyle = hand[3];
                    context.lineWidth = hand[2];
                    context.moveTo(face.cx, face.cy);
                    context.lineTo(face.cx + Math.sin(hand[0]) * hand[1], face.cy - Math.cos(hand[0]) * hand[1]);
                    context.stroke();
                }
                context.beginPath();
                context.fillStyle = "#7a480d";
                context.ellipse(face.cx - 4, face.cy - 4, 8, 8);
                context.fill();
            }
            Connections {
                target: scene
                function onClockTimeChanged() { clockHands.requestPaint(); }
                function onRoomIdChanged() { clockHands.requestPaint(); }
            }
        }

        Repeater {
            id: objects
            model: scene.currentRoom.hotspots || []
            delegate: Item {
                id: objectArea
                required property var modelData
                required property int index
                objectName: "hotspot_" + modelData.id
                x: modelData.rect[0]
                y: modelData.rect[1]
                width: modelData.rect[2]
                height: modelData.rect[3]
                z: modelData.action === "letter" ? 2 : 1
                Accessible.role: Accessible.Button
                Accessible.name: modelData.label
                Accessible.onPressAction: scene.useHotspot(modelData, false)
                Rectangle {
                    anchors.fill: parent
                    color: "transparent"
                    border.color: "#fff69a"
                    border.width: 3
                    visible: scene.showLabels || scene.selectedIndex === objectArea.index || actionMouse.containsMouse
                    opacity: actionMouse.containsMouse && !scene.showLabels ? 0.75 : 1
                }
                Rectangle {
                    anchors.centerIn: parent
                    width: objectLabel.implicitWidth + 22
                    height: objectLabel.implicitHeight + 12
                    color: "#ffffd7"
                    border.color: "#413014"
                    visible: scene.showLabels || scene.selectedIndex === objectArea.index
                    Text {
                        id: objectLabel
                        anchors.centerIn: parent
                        text: objectArea.modelData.label
                        font.family: "W95FA"
                        font.pixelSize: 23
                        color: "#000000"
                    }
                }
                MouseArea {
                    id: actionMouse
                    anchors.fill: parent
                    acceptedButtons: Qt.LeftButton
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onEntered: scene.speech = objectArea.modelData.room !== undefined
                        ? "Click the door to visit the " + objectArea.modelData.label + "."
                        : "Click to open " + objectArea.modelData.label + ". Shift-click to change it."
                    onClicked: mouse => {
                        scene.forceActiveFocus();
                        scene.useHotspot(objectArea.modelData, Boolean(mouse.modifiers & Qt.ShiftModifier));
                    }
                }
            }
        }

        Item {
            id: rover
            objectName: "roverCompanion"
            function containsPosePoint(point) {
                const scale = Math.min(width / 384, height / 288);
                const px = Math.floor((point.x - (width - 384 * scale) / 2) / (4 * scale));
                const py = Math.floor((point.y - (height - 288 * scale) / 2) / (4 * scale));
                const mask = Data.roverHitMasks[String(scene.poseId)];
                if (!mask || px < 0 || px >= 96 || py < 0 || py >= 72) return false;
                const spans = mask[py];
                for (let i = 0; i < spans.length; i += 2) {
                    if (px >= spans[i] && px < spans[i + 1]) return true;
                }
                return false;
            }
            x: scene.currentRoom.rover ? scene.currentRoom.rover.x : roomCanvas.width - 400
            y: scene.currentRoom.rover ? scene.currentRoom.rover.y : roomCanvas.height - 340
            width: scene.currentRoom.rover ? scene.currentRoom.rover.width : 360
            height: scene.currentRoom.rover ? scene.currentRoom.rover.height : 300
            z: 4
            Image {
                anchors.fill: parent
                source: scene.asset("rover-poses/pose_" + scene.poseId + ".png")
                fillMode: Image.PreserveAspectFit
                smooth: false
                cache: true
                asynchronous: true
                retainWhileLoading: true
            }
            MouseArea {
                anchors.fill: parent
                containmentMask: QtObject {
                    function contains(point: point): bool { return rover.containsPosePoint(point); }
                }
                acceptedButtons: Qt.LeftButton
                cursorShape: Qt.PointingHandCursor
                onClicked: scene.companionOpen ? scene.closeCompanion() : scene.showCompanion()
            }
            Accessible.role: Accessible.Button
            Accessible.name: "Rover. Click to ask me to do something."
            Accessible.onPressAction: scene.showCompanion()
        }

        Rectangle {
            id: bubble
            objectName: "roverBubble"
            x: Math.max(15, Math.min(roomCanvas.width - width - 15, rover.x - 55))
            y: Math.max(15, rover.y - height - 18 + (scene.currentRoom.speechOffsetY || 0))
            width: scene.companionOpen ? 450 : 405
            height: scene.companionOpen ? commandColumn.implicitHeight + 34 : 145
            radius: 16
            z: 5
            color: "#ffffe7"
            border.color: "#17130a"
            border.width: 2
            MouseArea {
                anchors.fill: parent
                visible: scene.companionOpen
                acceptedButtons: Qt.LeftButton
            }
            Text {
                visible: !scene.companionOpen
                anchors.fill: parent
                anchors.margins: 17
                text: scene.speech
                font.family: "Times New Roman"
                font.pixelSize: 24
                color: "#000000"
                wrapMode: Text.WordWrap
                verticalAlignment: Text.AlignVCenter
            }
            Column {
                id: commandColumn
                visible: scene.companionOpen
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 17
                spacing: 3
                Text {
                    width: parent.width
                    height: 42
                    text: "What would you like to do?"
                    font.family: "Times New Roman"
                    font.pixelSize: 26
                    font.bold: true
                    color: "#17130a"
                    verticalAlignment: Text.AlignVCenter
                }
                SpeechChoice {
                    id: programsChoice
                    objectName: "roverCommand_programs"
                    width: parent.width
                    text: "Open an app or folder…"
                    onClicked: scene.runCompanionCommand("programs")
                }
                SpeechChoice {
                    objectName: "roverCommand_rooms"
                    width: parent.width
                    text: "Go to another room…"
                    onClicked: scene.runCompanionCommand("rooms")
                }
                SpeechChoice {
                    objectName: "roverCommand_notes"
                    width: parent.width
                    text: "Write a note"
                    onClicked: scene.runCompanionCommand("notes")
                }
                SpeechChoice {
                    objectName: "roverCommand_calendar"
                    width: parent.width
                    text: "Open my calendar"
                    onClicked: scene.runCompanionCommand("calendar")
                }
                SpeechChoice {
                    objectName: "roverCommand_clock"
                    width: parent.width
                    text: "Set a timer"
                    onClicked: scene.runCompanionCommand("clock")
                }
                SpeechChoice {
                    objectName: "roverCommand_options"
                    width: parent.width
                    text: "Change room options…"
                    onClicked: scene.runCompanionCommand("options")
                }
                SpeechChoice {
                    objectName: "roverCommand_trick"
                    width: parent.width
                    text: "Do a trick!"
                    onClicked: scene.runCompanionCommand("trick")
                }
                SpeechChoice {
                    objectName: "roverCommand_cancel"
                    width: parent.width
                    text: "Never mind"
                    onClicked: scene.closeCompanion()
                }
            }
            Canvas {
                x: parent.width * 0.52
                y: parent.height - 2
                width: 32
                height: 28
                onPaint: {
                    const ctx = getContext("2d");
                    ctx.clearRect(0, 0, width, height);
                    ctx.beginPath();
                    ctx.moveTo(0, 0);
                    ctx.lineTo(28, 24);
                    ctx.lineTo(17, 0);
                    ctx.fillStyle = "#ffffe7";
                    ctx.fill();
                    ctx.strokeStyle = "#17130a";
                    ctx.lineWidth = 2;
                    ctx.stroke();
                }
            }
        }
    }

    Rectangle {
        id: toolbar
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.leftMargin: 16
        anchors.bottomMargin: 64
        width: toolRow.implicitWidth + 12
        height: toolRow.implicitHeight + 12
        color: "#c0c0c0"
        border.color: "#ffffff"
        border.width: 2
        Row {
            id: toolRow
            anchors.centerIn: parent
            spacing: 5
            RetroButton { text: "Rooms…"; onClicked: scene.showRoomChooser() }
            RetroButton {
                text: scene.showLabels ? "Hide names" : "Objects"
                onClicked: scene.labelsRequested(!scene.showLabels)
            }
            RetroButton { text: "Options…"; onClicked: scene.showOptions() }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: scene.currentRoom.name || "Bob House KDE"
                color: "#000000"
                font.family: "W95FA"
                font.pixelSize: 16
                leftPadding: 8
                rightPadding: 10
            }
        }
    }

    Controls.Popup {
        id: optionsMenu
        objectName: "roomOptions"
        anchors.centerIn: parent
        width: Math.min(scene.width - 32, 470)
        padding: 16
        modal: false
        focus: true
        closePolicy: Controls.Popup.CloseOnEscape | Controls.Popup.CloseOnPressOutside
        background: Rectangle { color: "#c0c0c0"; border.color: "#ffffff"; border.width: 3 }
        contentItem: ColumnLayout {
            spacing: 14
            Rectangle {
                Layout.fillWidth: true
                height: 32
                color: "#000080"
                Text { anchors.centerIn: parent; text: "Room options"; color: "#ffffff"; font.family: "W95FA"; font.pixelSize: 18 }
            }
            Controls.CheckBox {
                text: "Animate Rover and the room"
                checked: scene.animations
                font.family: "W95FA"
                font.pixelSize: 17
                palette.windowText: "#000000"
                onClicked: scene.animationsRequested(checked)
            }
            Controls.CheckBox {
                text: "Show object names"
                checked: scene.showLabels
                font.family: "W95FA"
                font.pixelSize: 17
                palette.windowText: "#000000"
                onClicked: scene.labelsRequested(checked)
            }
            Text {
                Layout.fillWidth: true
                text: "Shift-click an object to choose the app, folder, or link it opens. Right-click anywhere for the normal KDE desktop menu."
                color: "#000000"
                font.family: "W95FA"
                font.pixelSize: 17
                wrapMode: Text.WordWrap
            }
            RowLayout {
                Layout.alignment: Qt.AlignRight
                RetroButton { text: "Help…"; onClicked: scene.openAction("help", false) }
                RetroButton { text: "OK"; onClicked: optionsMenu.close() }
            }
        }
    }

    Controls.Popup {
        id: roomMenu
        objectName: "roomChooser"
        anchors.centerIn: parent
        width: Math.min(scene.width - 32, 570)
        height: Math.min(scene.height - 48, roomColumn.implicitHeight + 28)
        padding: 14
        modal: false
        focus: true
        closePolicy: Controls.Popup.CloseOnEscape | Controls.Popup.CloseOnPressOutside
        background: Rectangle { color: "#c0c0c0"; border.color: "#ffffff"; border.width: 3 }
        contentItem: ColumnLayout {
            id: roomColumn
            spacing: 12
            Rectangle {
                Layout.fillWidth: true
                height: 32
                color: "#000080"
                Text { anchors.centerIn: parent; text: "Which room would you like to visit?"; color: "#ffffff"; font.family: "W95FA"; font.pixelSize: 18 }
            }
            Controls.ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                implicitHeight: roomGrid.implicitHeight
                contentWidth: availableWidth
                GridLayout {
                    id: roomGrid
                    width: parent.width
                    columns: 2
                    rowSpacing: 7
                    columnSpacing: 7
                    Repeater {
                        model: scene.roomList
                        RetroButton {
                            required property var modelData
                            text: modelData.name
                            Layout.fillWidth: true
                            emphasized: String(modelData.id) === String(scene.currentRoom.id)
                            onClicked: scene.goToRoom(modelData.id)
                        }
                    }
                }
            }
            RetroButton { text: "Back to the room"; Layout.alignment: Qt.AlignRight; onClicked: roomMenu.close() }
        }
    }

    Timer {
        interval: 40
        running: scene.visible && scene.animations
        repeat: true
        onTriggered: {
            scene.animationTime = Date.now();
            scene.poseId = Rover.frame(scene.actor, scene.animationTime, true);
        }
    }
    Timer {
        interval: 1000
        running: scene.visible
        repeat: true
        onTriggered: scene.clockTime = Date.now()
    }
}
