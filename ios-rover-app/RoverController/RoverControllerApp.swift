import SwiftUI

@main
struct RoverControllerApp: App {
    @StateObject private var hub = HubManager()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(hub)
                .preferredColorScheme(.dark)
        }
    }
}
