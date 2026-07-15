import SwiftUI

struct ScanView: View {
    @EnvironmentObject var hub: HubManager

    var body: some View {
        NavigationView {
            VStack(spacing: 16) {
                statusBanner
                    .padding(.horizontal)

                List(hub.discovered) { d in
                    Button {
                        hub.connect(to: d)
                    } label: {
                        HStack {
                            VStack(alignment: .leading) {
                                Text(d.name).bold()
                                Text("RSSI \(d.rssi)").font(.caption).foregroundColor(.secondary)
                            }
                            Spacer()
                            Image(systemName: "chevron.right")
                        }
                    }
                }
                .listStyle(.plain)

                HStack(spacing: 12) {
                    Button("Scan for hubs") { hub.startScan() }
                        .buttonStyle(BrickButtonStyle(color: LegoTheme.blue))
                    if case .connected = hub.connectionState {
                        Button("Disconnect") { hub.disconnect() }
                            .buttonStyle(BrickButtonStyle(color: LegoTheme.red))
                    }
                }
                .padding(.horizontal)
                .padding(.bottom)
            }
            .background(LegoTheme.background.ignoresSafeArea())
            .navigationTitle("LEGO Rover")
        }
        .navigationViewStyle(.stack)
    }

    @ViewBuilder
    private var statusBanner: some View {
        switch hub.connectionState {
        case .disconnected:
            Text("Not connected").foregroundColor(.secondary)
        case .scanning:
            Text("Scanning…").foregroundColor(LegoTheme.yellow)
        case .connecting:
            Text("Connecting…").foregroundColor(LegoTheme.yellow)
        case .connected(let name):
            Text("Connected: \(name)").foregroundColor(LegoTheme.green).bold()
        }
    }
}
