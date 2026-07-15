import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var hub: HubManager

    var body: some View {
        NavigationView {
            Form {
                Section("Ports") {
                    Picker("Claw port", selection: $hub.clawPort) {
                        Text("C").tag(LWP3.Port.c)
                        Text("D").tag(LWP3.Port.d)
                    }
                    Picker("Head port", selection: $hub.headPort) {
                        Text("C").tag(LWP3.Port.c)
                        Text("D").tag(LWP3.Port.d)
                    }
                    if hub.clawPort == hub.headPort {
                        Text("Claw and head are set to the same port — fix this before testing.")
                            .font(.caption)
                            .foregroundColor(LegoTheme.red)
                    }
                }
                Section("Drive") {
                    Stepper("Speed: \(hub.driveSpeed)", value: Binding(
                        get: { Int(hub.driveSpeed) },
                        set: { hub.driveSpeed = Int8(clamping: $0) }
                    ), in: 10...100, step: 10)
                    Stepper(String(format: "Drive duration: %.1fs", hub.driveSeconds),
                            value: $hub.driveSeconds, in: 0.5...5, step: 0.5)
                    Stepper(String(format: "Turn duration: %.1fs", hub.turnSeconds),
                            value: $hub.turnSeconds, in: 0.3...3, step: 0.1)
                }
            }
            .navigationTitle("Settings")
        }
        .navigationViewStyle(.stack)
    }
}
