import SwiftUI

struct ContentView: View {
    var body: some View {
        TabView {
            ScanView()
                .tabItem { Label("Connect", systemImage: "antenna.radiowaves.left.and.right") }
            ControllerView()
                .tabItem { Label("Controller", systemImage: "gamecontroller") }
            ConsoleView()
                .tabItem { Label("Console", systemImage: "terminal") }
            SettingsView()
                .tabItem { Label("Settings", systemImage: "slider.horizontal.3") }
        }
        .tint(LegoTheme.yellow)
    }
}
