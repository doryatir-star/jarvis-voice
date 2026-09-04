import SwiftUI

struct ConnectView: View {
    @EnvironmentObject var cozmo: CozmoManager

    var body: some View {
        NavigationView {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    statusBanner

                    VStack(alignment: .leading, spacing: 10) {
                        Text("Before connecting").font(.headline).foregroundColor(CozmoTheme.orange)
                        step(1, "Put Cozmo on his charger to wake him.")
                        step(2, "Raise and lower his lift — his screen shows a Wi-Fi network name and password.")
                        step(3, "In iOS Settings, join THAT Wi-Fi network with this iPhone (not your home Wi-Fi).")
                        step(4, "Come back here and tap Connect.")
                    }
                    .padding()
                    .background(Color.black.opacity(0.25))
                    .clipShape(RoundedRectangle(cornerRadius: 12))

                    Button("Open Wi-Fi Settings") {
                        if let url = URL(string: UIApplication.openSettingsURLString) {
                            UIApplication.shared.open(url)
                        }
                    }
                    .buttonStyle(CozmoButtonStyle(color: .gray))

                    HStack(spacing: 12) {
                        Button("Connect") { cozmo.connect() }
                            .buttonStyle(CozmoButtonStyle(color: CozmoTheme.blue))
                        Button("Disconnect") { cozmo.disconnect() }
                            .buttonStyle(CozmoButtonStyle(color: CozmoTheme.red))
                    }
                }
                .padding()
            }
            .background(CozmoTheme.background.ignoresSafeArea())
            .navigationTitle("Cozmo")
        }
        .navigationViewStyle(.stack)
    }

    private func step(_ n: Int, _ text: String) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Text("\(n).").bold().foregroundColor(CozmoTheme.orange)
            Text(text)
        }
        .font(.subheadline)
    }

    @ViewBuilder
    private var statusBanner: some View {
        switch cozmo.connectionState {
        case .disconnected:
            Text("Not connected").foregroundColor(.secondary)
        case .connecting:
            Text("Connecting…").foregroundColor(CozmoTheme.orange)
        case .handshaking:
            Text("Talking to Cozmo…").foregroundColor(CozmoTheme.orange)
        case .ready:
            Text("Connected — Cozmo is ready").foregroundColor(CozmoTheme.green).bold()
        }
    }
}
