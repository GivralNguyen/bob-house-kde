import QtQuick
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami
import "Data.js" as Data

Kirigami.FormLayout {
    id: root
    twinFormLayouts: parentLayout
    property alias formLayout: root
    property string cfg_AssetRoot
    property string cfg_RoomId
    property alias cfg_Animations: animationCheck.checked
    property alias cfg_ShowLabels: labelsCheck.checked

    Controls.ComboBox {
        id: rooms
        Kirigami.FormData.label: "Room:"
        model: Data.rooms.rooms || []
        textRole: "name"
        valueRole: "id"
        currentIndex: {
            for (let i = 0; i < count; i++) {
                if (String(valueAt(i)) === root.cfg_RoomId) return i;
            }
            return 0;
        }
        onActivated: root.cfg_RoomId = String(currentValue)
    }
    Controls.CheckBox {
        id: animationCheck
        text: "Animate Rover and the room"
    }
    Controls.CheckBox {
        id: labelsCheck
        text: "Show object names"
    }
    Controls.TextField {
        Kirigami.FormData.label: "Artwork folder:"
        text: root.cfg_AssetRoot
        placeholderText: "file:///path/to/bob-house-kde/assets/"
        onTextEdited: root.cfg_AssetRoot = text
    }
    Controls.Label {
        text: "Click doors to walk between rooms. Shift-click an object to change what it opens. Right-click keeps the normal desktop menu."
        wrapMode: Text.WordWrap
        LayoutMirroring.enabled: false
        implicitWidth: 400
    }
}
