import QtQuick
import QtQuick.Controls

Button {
    id: button
    property bool emphasized: false
    padding: 7
    leftPadding: 13
    rightPadding: 13
    hoverEnabled: true
    font.family: "W95FA"
    font.pixelSize: 16
    contentItem: Text {
        text: button.text
        font: button.font
        color: button.emphasized ? "#ffffff" : "#15110c"
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    background: Rectangle {
        implicitWidth: 85
        implicitHeight: 34
        color: button.emphasized ? "#000080" : "#c0c0c0"
        border.color: button.down ? "#444444" : "#ffffff"
        border.width: 2
        Rectangle {
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            width: parent.width - 2
            height: 2
            color: button.down ? "#ffffff" : "#444444"
        }
        Rectangle {
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            width: 2
            height: parent.height - 2
            color: button.down ? "#ffffff" : "#444444"
        }
        Rectangle {
            anchors.fill: parent
            anchors.margins: 4
            visible: button.activeFocus
            color: "transparent"
            border.color: button.emphasized ? "#ffffff" : "#222222"
        }
    }
}
