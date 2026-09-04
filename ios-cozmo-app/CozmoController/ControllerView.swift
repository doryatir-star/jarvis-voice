import SwiftUI

struct ControllerView: View {
    @EnvironmentObject var cozmo: CozmoManager

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                Text(connectionLabel)
                    .font(.caption)
                    .foregroundColor(.secondary)

                driveGroup
                headGroup
                liftGroup
                lightsGroup
            }
            .padding()
        }
        .background(CozmoTheme.background.ignoresSafeArea())
    }

    private var connectionLabel: String {
        cozmo.connectionState == .ready ? "Driving Cozmo" : "Not connected — go to the Connect tab first"
    }

    private var driveGroup: some View {
        VStack(spacing: 10) {
            sectionTitle("DRIVE")
            Button("▲ Forward") { cozmo.drive(.forward) }
                .buttonStyle(CozmoButtonStyle(color: CozmoTheme.green))
            HStack(spacing: 10) {
                Button("◀ Left") { cozmo.turn(.left) }
                    .buttonStyle(CozmoButtonStyle(color: CozmoTheme.blue))
                Button("■ Stop") { cozmo.stopAll() }
                    .buttonStyle(CozmoButtonStyle(color: CozmoTheme.red))
                Button("Right ▶") { cozmo.turn(.right) }
                    .buttonStyle(CozmoButtonStyle(color: CozmoTheme.blue))
            }
            Button("▼ Backward") { cozmo.drive(.backward) }
                .buttonStyle(CozmoButtonStyle(color: CozmoTheme.green))
        }
    }

    private var headGroup: some View {
        VStack(spacing: 10) {
            sectionTitle("HEAD")
            HStack(spacing: 10) {
                Button("Look Down") { cozmo.turnHead(.down) }.buttonStyle(CozmoButtonStyle())
                Button("Center") { cozmo.turnHead(.center) }.buttonStyle(CozmoButtonStyle())
                Button("Look Up") { cozmo.turnHead(.up) }.buttonStyle(CozmoButtonStyle())
            }
        }
    }

    private var liftGroup: some View {
        VStack(spacing: 10) {
            sectionTitle("LIFT")
            HStack(spacing: 10) {
                Button("Lift Down") { cozmo.lift(.down) }.buttonStyle(CozmoButtonStyle())
                Button("Lift Up") { cozmo.lift(.up) }.buttonStyle(CozmoButtonStyle())
            }
        }
    }

    private var lightsGroup: some View {
        VStack(spacing: 10) {
            sectionTitle("BACKPACK LIGHTS")
            HStack(spacing: 10) {
                lightButton("Green", .green, CozmoTheme.green)
                lightButton("Red", .red, CozmoTheme.red)
                lightButton("Blue", .blue, CozmoTheme.blue)
            }
            HStack(spacing: 10) {
                lightButton("White", .white, .white)
                lightButton("Off", .off, .gray)
            }
        }
    }

    private enum LightColor: String { case green, red, blue, white, off }

    private func lightButton(_ title: String, _ color: LightColor, _ swatch: Color) -> some View {
        Button(title) { cozmo.lights(color.rawValue) }
            .buttonStyle(CozmoButtonStyle(color: swatch))
    }

    private func sectionTitle(_ text: String) -> some View {
        Text(text)
            .font(.headline)
            .foregroundColor(CozmoTheme.orange)
    }
}
