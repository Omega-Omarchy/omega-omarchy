import QtQuick

Item {
    id: root
    width: 18
    height: 18

    Rectangle {
        anchors.fill: parent
        radius: 2
        color: "#1a1b26"
        border.color: "#b9f27c"
        Text {
            anchors.centerIn: parent
            text: "Ω"
            color: "#b9f27c"
            font.pixelSize: 12
        }
    }

    MouseArea {
        anchors.fill: parent
        onClicked: {
            if (typeof Omarchy !== "undefined" && Omarchy.openPanel) {
                Omarchy.openPanel("omega.omarchy")
            }
        }
    }
}
