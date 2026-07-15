import SwiftUI

struct ControllerView: View {
    @EnvironmentObject var hub: HubManager

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                Text(connectionLabel)
                    .font(.caption)
                    .foregroundColor(.secondary)

                driveGroup
                headGroup
                clawGroup
                nudgeGroup
            }
            .padding()
        }
        .background(LegoTheme.background.ignoresSafeArea())
    }

    private var connectionLabel: String {
        if case .connected(let name) = hub.connectionState {
            return "Driving \(name)"
        }
        return "Not connected — go to the Connect tab first"
    }

    private var driveGroup: some View {
        VStack(spacing: 10) {
            sectionTitle("DRIVE")
            Button("▲ Forward") { hub.drive(.forward) }
                .buttonStyle(BrickButtonStyle(color: LegoTheme.green))
            HStack(spacing: 10) {
                Button("◀ Left") { hub.turn(.left) }
                    .buttonStyle(BrickButtonStyle(color: LegoTheme.blue))
                Button("■ Stop") { hub.stopAll() }
                    .buttonStyle(BrickButtonStyle(color: LegoTheme.red))
                Button("Right ▶") { hub.turn(.right) }
                    .buttonStyle(BrickButtonStyle(color: LegoTheme.blue))
            }
            Button("▼ Backward") { hub.drive(.backward) }
                .buttonStyle(BrickButtonStyle(color: LegoTheme.green))
        }
    }

    private var headGroup: some View {
        VStack(spacing: 10) {
            sectionTitle("HEAD")
            HStack(spacing: 10) {
                Button("Look Left") { hub.turnHead(.left) }.buttonStyle(BrickButtonStyle())
                Button("Center") { hub.turnHead(.center) }.buttonStyle(BrickButtonStyle())
                Button("Look Right") { hub.turnHead(.right) }.buttonStyle(BrickButtonStyle())
            }
        }
    }

    private var clawGroup: some View {
        VStack(spacing: 10) {
            sectionTitle("CLAW")
            HStack(spacing: 10) {
                Button("Open") { hub.claw(.open) }.buttonStyle(BrickButtonStyle())
                Button("Close") { hub.claw(.close) }.buttonStyle(BrickButtonStyle())
            }
        }
    }

    private var nudgeGroup: some View {
        VStack(spacing: 10) {
            sectionTitle("PORT TEST")
            HStack(spacing: 10) {
                Button("Nudge Port C") { hub.nudge(port: LWP3.Port.c) }
                    .buttonStyle(BrickButtonStyle(color: .gray))
                Button("Nudge Port D") { hub.nudge(port: LWP3.Port.d) }
                    .buttonStyle(BrickButtonStyle(color: .gray))
            }
            Text("Watch which motor moves, then set Claw/Head port in Settings.")
                .font(.caption2)
                .foregroundColor(.secondary)
        }
    }

    private func sectionTitle(_ text: String) -> some View {
        Text(text)
            .font(.headline)
            .foregroundColor(LegoTheme.yellow)
    }
}
