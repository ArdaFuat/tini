import QtQuick
import QtQuick.Window

Item {
    id: root
    width: 144
    height: 144
    property real speechLevel: 0
    property real expansion: 1
    property color orbColor: "#91a3d4"
    property int mode: 3
    property bool running: true

    ShaderEffect {
        id: mesh
        objectName: "orbMesh"
        anchors.fill: parent
        property real clock: 0
        property real voice: root.speechLevel
        property real openness: root.expansion
        property real tintR: root.orbColor.r
        property real tintG: root.orbColor.g
        property real tintB: root.orbColor.b
        property real state: root.mode
        property real pixelRatio: Screen.devicePixelRatio
        mesh: GridMesh { resolution: Qt.size(34, 17) }
        vertexShader: Qt.resolvedUrl("wire.vert.qsb")
        fragmentShader: Qt.resolvedUrl("wire.frag.qsb")

        Behavior on openness {
            NumberAnimation { duration: 260; easing.type: Easing.OutCubic }
        }
        Behavior on voice {
            id: voiceResponse
            // Match the former 45 ms attack / 380 ms release envelope. For
            // OutCubic, the initial response time is about duration / 3.
            NumberAnimation {
                duration: voiceResponse.targetValue > mesh.voice ? 135 : 1140
                easing.type: Easing.OutCubic
            }
        }
        Behavior on tintR { NumberAnimation { duration: 180 } }
        Behavior on tintG { NumberAnimation { duration: 180 } }
        Behavior on tintB { NumberAnimation { duration: 180 } }

        // Animator jobs run on Qt's native render thread. Neither dictation nor
        // a late Python/GUI callback is needed to advance the orb's motion.
        UniformAnimator {
            target: mesh
            uniform: "clock"
            from: 0
            // All shader frequencies repeat after this period, so leaving the
            // app open for hours never introduces a jump at the loop boundary.
            to: 6283.185307179586
            duration: 6283185
            loops: Animation.Infinite
            running: root.running
        }
    }
}
