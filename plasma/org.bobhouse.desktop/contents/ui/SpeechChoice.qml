import QtQuick
import QtQuick.Controls as Controls

Controls.Button {
    id: choice
    implicitHeight: 42
    leftPadding: 34
    rightPadding: 8
    topPadding: 5
    bottomPadding: 5
    hoverEnabled: true
    font.family: "Times New Roman"
    font.pixelSize: 25
    Keys.onReturnPressed: event => {
        if (enabled) clicked();
        event.accepted = true;
    }
    Keys.onEnterPressed: event => {
        if (enabled) clicked();
        event.accepted = true;
    }
    contentItem: Text {
        text: choice.text
        font: choice.font
        color: "#17130a"
        verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
        radius: 5
        color: choice.down ? "#f5d96f" : choice.hovered ? "#fff0ac" : "transparent"
        border.width: choice.visualFocus ? 1 : 0
        border.color: "#73551c"
        Rectangle {
            x: 8
            anchors.verticalCenter: parent.verticalCenter
            width: 18
            height: 18
            radius: 9
            color: "#fff5b6"
            border.color: "#755016"
            border.width: 1
            Rectangle {
                anchors.centerIn: parent
                width: 10
                height: 10
                radius: 5
                color: choice.hovered || choice.visualFocus ? "#f0b633" : "#ffffe7"
                border.color: "#ba9946"
            }
        }
    }
}
