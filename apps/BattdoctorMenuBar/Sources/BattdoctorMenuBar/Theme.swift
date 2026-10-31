import SwiftUI

enum Brand {
    static let indigo = Color(red: 0.36, green: 0.32, blue: 0.92)
    static let teal = Color(red: 0.08, green: 0.72, blue: 0.68)
    static let coral = Color(red: 0.94, green: 0.34, blue: 0.34)
    static let amber = Color(red: 0.96, green: 0.62, blue: 0.18)

    static func canvas(_ scheme: ColorScheme) -> Color {
        scheme == .dark
            ? Color(red: 0.07, green: 0.07, blue: 0.10)
            : Color(red: 0.975, green: 0.975, blue: 0.995)
    }

    static func card(_ scheme: ColorScheme) -> Color {
        scheme == .dark ? Color.white.opacity(0.06) : Color.black.opacity(0.035)
    }

    static func cardStroke(_ scheme: ColorScheme) -> Color {
        scheme == .dark ? Color.white.opacity(0.09) : Color.black.opacity(0.06)
    }

    static func accentGradient(_ scheme: ColorScheme) -> LinearGradient {
        let start = scheme == .dark ? indigo : Color(red: 0.28, green: 0.24, blue: 0.82)
        let end = scheme == .dark ? teal : Color(red: 0.05, green: 0.60, blue: 0.62)
        return LinearGradient(colors: [start, end], startPoint: .topLeading, endPoint: .bottomTrailing)
    }

    static func gaugeGradient(_ scheme: ColorScheme) -> AngularGradient {
        let start = scheme == .dark ? indigo : Color(red: 0.28, green: 0.24, blue: 0.82)
        let end = scheme == .dark ? teal : Color(red: 0.05, green: 0.60, blue: 0.62)
        return AngularGradient(colors: [start, end, start], center: .center)
    }
}
