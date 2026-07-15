import SwiftUI

enum LegoTheme {
    static let red = Color(red: 0.816, green: 0.063, blue: 0.071)     // LEGO red #D01012
    static let yellow = Color(red: 1.0, green: 0.835, blue: 0.0)      // LEGO yellow #FFD500
    static let blue = Color(red: 0.0, green: 0.333, blue: 0.75)       // LEGO blue #0055BF
    static let green = Color(red: 0.137, green: 0.471, blue: 0.255)   // LEGO green #237841
    static let background = Color(red: 0.086, green: 0.086, blue: 0.098)
}

/// Chunky, rounded "brick" button look used throughout the controller.
struct BrickButtonStyle: ButtonStyle {
    var color: Color = LegoTheme.yellow

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
