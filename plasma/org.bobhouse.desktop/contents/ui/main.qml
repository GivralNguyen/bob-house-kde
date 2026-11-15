import QtQuick
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasmoid

WallpaperItem {
    id: wallpaper
    accentColor: "#bd7621"

    function saveValue(name, value) {
        wallpaper.configuration[name] = value;
        wallpaper.configuration.writeConfig();
    }

    contextualActions: [roverAction, roomsAction, labelsAction, optionsAction, helpAction]
    PlasmaCore.Action {
        id: roverAction
        text: "Bob: Ask Rover…"
        icon.name: "help-hint"
        onTriggered: scene.showCompanion()
    }
    PlasmaCore.Action {
        id: roomsAction
        text: "Bob: Go to another room…"
        icon.name: "user-home"
        onTriggered: scene.showRoomChooser()
    }
    PlasmaCore.Action {
        id: labelsAction
        text: "Bob: Show object names"
        icon.name: "help-hint"
        checkable: true
        checked: wallpaper.configuration.ShowLabels
        onTriggered: wallpaper.saveValue("ShowLabels", !wallpaper.configuration.ShowLabels)
    }
    PlasmaCore.Action {
        id: optionsAction
        text: "Bob: Room options…"
        icon.name: "configure"
        onTriggered: scene.showOptions()
    }
    PlasmaCore.Action {
        id: helpAction
        text: "Bob: Help"
        icon.name: "help-contents"
        onTriggered: scene.openAction("help", false)
    }

    RoomScene {
        id: scene
        anchors.fill: parent
        assetRoot: String(wallpaper.configuration.AssetRoot)
        roomId: String(wallpaper.configuration.RoomId)
        animations: wallpaper.configuration.Animations
        showLabels: wallpaper.configuration.ShowLabels
        onRoomRequested: roomId => wallpaper.saveValue("RoomId", roomId)
        onLabelsRequested: show => wallpaper.saveValue("ShowLabels", show)
        onAnimationsRequested: animate => wallpaper.saveValue("Animations", animate)
    }
}
