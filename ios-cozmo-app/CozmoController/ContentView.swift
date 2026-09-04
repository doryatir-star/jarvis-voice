import SwiftUI

struct ContentView: View {
    var body: some View {
        TabView {
            ConnectView()
                .tabItem { Label("Connect", systemImage: "wifi") }
            ControllerView()
                .tabItem { Label("Controller", systemImage: "gamecontroller") }
            ConsoleView()
                .tabItem { Label("Console", systemImage: "terminal") }
            SettingsView()
                .tabItem { Label("Settings", systemImage: "slider.horizontal.3") }
        }
        .tint(CozmoTheme.orange)
    }
}
