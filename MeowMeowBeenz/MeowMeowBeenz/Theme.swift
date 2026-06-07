import SwiftUI

// MARK: - Risk level styling

enum Risk: String {
    case normal, watch, review

    init(_ raw: String) { self = Risk(rawValue: raw) ?? .normal }

    var color: Color {
        switch self {
        case .normal: return .green
        case .watch: return .orange
        case .review: return .red
        }
    }

    var label: String {
        switch self {
        case .normal: return "Normal"
        case .watch: return "Watch"
        case .review: return "Review"
        }
    }
}

/// A small colored capsule used for status, mirroring the web app's risk badges.
struct RiskBadge: View {
    let level: String
    var body: some View {
        let risk = Risk(level)
        Text(risk.label)
            .font(.caption.weight(.semibold))
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .background(risk.color.opacity(0.18), in: Capsule())
            .foregroundStyle(risk.color)
    }
}

// MARK: - Shared presentation primitives

struct AppBackdrop: View {
    var body: some View {
        ZStack {
            LinearGradient(
                colors: [
                    Color(red: 0.96, green: 0.98, blue: 1.00),
                    Color(red: 0.94, green: 0.96, blue: 1.00),
                    Color(red: 0.99, green: 0.97, blue: 0.98)
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()

            Circle()
                .fill(Color.pink.opacity(0.10))
                .frame(width: 250, height: 250)
                .blur(radius: 50)
                .offset(x: -120, y: -170)

            Circle()
                .fill(Color.mint.opacity(0.13))
                .frame(width: 280, height: 280)
                .blur(radius: 52)
                .offset(x: 130, y: 220)
        }
    }
}

struct SoftCard<Content: View>: View {
    let title: String?
    let subtitle: String?
    let icon: String?
    let accent: Color
    let content: Content

    init(
        title: String? = nil,
        subtitle: String? = nil,
        icon: String? = nil,
        accent: Color = .blue,
        @ViewBuilder content: () -> Content
    ) {
        self.title = title
        self.subtitle = subtitle
        self.icon = icon
        self.accent = accent
        self.content = content()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            if let title {
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    if let icon {
                        Image(systemName: icon)
                            .foregroundStyle(accent)
                            .font(.callout.weight(.semibold))
                    }
                    VStack(alignment: .leading, spacing: 2) {
                        Text(title)
                            .font(.headline.weight(.semibold))
                        if let subtitle {
                            Text(subtitle)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
            }
            content
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .stroke(Color.white.opacity(0.45), lineWidth: 0.8)
        )
        .shadow(color: .black.opacity(0.08), radius: 12, x: 0, y: 4)
    }
}

struct SoftChip: View {
    let text: String
    let tone: Color

    var body: some View {
        Text(text)
            .font(.caption2.weight(.semibold))
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .background(tone.opacity(0.16), in: Capsule())
            .foregroundStyle(tone)
    }
}

// Hex color helper for accent strings from backend payloads.
extension Color {
    init(hex: String) {
        let cleaned = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var value: UInt64 = 0
        Scanner(string: cleaned).scanHexInt64(&value)
        let r = Double((value >> 16) & 0xFF) / 255
        let g = Double((value >> 8) & 0xFF) / 255
        let b = Double(value & 0xFF) / 255
        self.init(red: r, green: g, blue: b)
    }
}

// MARK: - Formatting helpers

enum Format {
    nonisolated(unsafe) private static let iso: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()

    nonisolated(unsafe) private static let isoNoFraction = ISO8601DateFormatter()

    static func date(_ raw: String) -> Date? {
        iso.date(from: raw) ?? isoNoFraction.date(from: raw)
    }

    /// "8:42 PM" style clock label for an ISO timestamp.
    static func clock(_ raw: String) -> String {
        guard let date = date(raw) else { return "" }
        return date.formatted(date: .omitted, time: .shortened)
    }

    /// "Today, 8:42 PM" / "Mon, 8:42 PM" relative label.
    static func relative(_ raw: String) -> String {
        guard let date = date(raw) else { return raw }
        if Calendar.current.isDateInToday(date) {
            return "Today, \(date.formatted(date: .omitted, time: .shortened))"
        }
        return date.formatted(.dateTime.weekday(.abbreviated).hour().minute())
    }

    static func percent(_ value: Double) -> String {
        "\(Int((value * 100).rounded()))%"
    }

    /// Turn "active_playfight.playing" / "repeated_meow" into "Active playfight playing".
    static func humanize(_ token: String) -> String {
        token
            .replacingOccurrences(of: "_", with: " ")
            .replacingOccurrences(of: ".", with: " ")
            .capitalized
    }
}
