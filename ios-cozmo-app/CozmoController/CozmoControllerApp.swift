import SwiftUI

@main
struct CozmoControllerApp: App {
    @StateObject private var cozmo = CozmoManager()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(cozmo)
                .preferredColorScheme(.dark)
        }
    }
}
