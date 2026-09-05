import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var cozmo: CozmoManager

    var body: some View {
        NavigationView {
            Form {
                Section("Drive") {
                    Stepper(String(format: "Drive speed: %.0f mm/s", cozmo.driveSpeed),
                            value: $cozmo.driveSpeed, in: 20...200, step: 10)
                    Stepper(String(format: "Turn speed: %.0f mm/s", cozmo.turnSpeed),
                            value: $cozmo.turnSpeed, in: 20...200, step: 10)
                    Stepper(String(format: "Drive duration: %.1fs", cozmo.driveSeconds),
                            value: $cozmo.driveSeconds, in: 0.5...5, step: 0.5)
                    Stepper(String(format: "Turn duration: %.1fs", cozmo.turnSeconds),
                            value: $cozmo.turnSeconds, in: 0.3...3, step: 0.1)
                }
                Section("About") {
                    Text("Cozmo's max wheel speed is 200 mm/s. Head and lift always move to a " +
                         "fixed up/down/center position — there's no speed setting for those.")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            .navigationTitle("Settings")
        }
        .navigationViewStyle(.stack)
    }
}
