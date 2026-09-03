import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Omarchy shell panel. Launch is a subprocess of the game binary; this file
// does not embed the game runtime. Theme colors come from the shell.
Item {
    id: root
    property string gameCommand: "omega-omarchy"
    width: 280
    height: 160

    Rectangle {
        anchors.fill: parent
        color: "#1a1b26"
        border.color: "#9ece6a"
        radius: 6

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 8

            Text {
                text: "OMEGA OMARCHY"
                color: "#b9f27c"
                font.family: "JetBrains Mono"
                font.pixelSize: 16
            }
            Text {
                text: "The Revolution Will Be Customized"
                color: "#449dab"
                font.family: "JetBrains Mono"
                font.pixelSize: 11
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            Button {
                text: "Play Now"
                onClicked: {
                    // The shell executes the separately packaged game.
                    if (typeof Omarchy !== "undefined" && Omarchy.runCommand) {
                        Omarchy.runCommand(root.gameCommand)
                    }
                }
            }
            Text {
                text: "Limitless stays optional. Sharing stays local until you say otherwise."
                color: "#565f89"
                font.pixelSize: 10
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
        }
    }
}
