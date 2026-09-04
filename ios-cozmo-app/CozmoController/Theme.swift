import SwiftUI

enum CozmoTheme {
    static let orange = Color(red: 0.95, green: 0.45, blue: 0.05)     // Cozmo body orange
    static let blue = Color(red: 0.0, green: 0.6, blue: 0.85)
    static let green = Color(red: 0.16, green: 0.6, blue: 0.35)
    static let red = Color(red: 0.85, green: 0.16, blue: 0.16)
    static let background = Color(red: 0.07, green: 0.07, blue: 0.09)
}

/// Chunky, rounded button look, matching the LEGO rover app's controller feel.
struct CozmoButtonStyle: ButtonStyle {
    var color: Color = CozmoTheme.orange

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 18, weight: .heavy))
            .foregroundColor(.black)
            .frame(maxWidth: .infinity, minHeight: 54)
            .background(color)
            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .stroke(Color.black.opacity(0.25), lineWidth: 2)
            )
            .scaleEffect(configuration.isPressed ? 0.94 : 1.0)
            .opacity(configuration.isPressed ? 0.85 : 1.0)
    }
}
