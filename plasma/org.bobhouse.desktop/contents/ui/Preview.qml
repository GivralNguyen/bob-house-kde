import QtQuick
import QtQuick.Window

Window {
    width: 1200
    height: 900
    visible: true
    title: "Bob House KDE — wallpaper preview"
    RoomScene {
        id: room
        anchors.fill: parent
        assetRoot: Qt.resolvedUrl("../../../../assets/").toString()
        launchEnabled: false
        onRoomRequested: id => room.roomId = id
        onLabelsRequested: show => room.showLabels = show
        onAnimationsRequested: animate => room.animations = animate
        onActionRequested: url => console.log("Preview action:", url)
    }
}
