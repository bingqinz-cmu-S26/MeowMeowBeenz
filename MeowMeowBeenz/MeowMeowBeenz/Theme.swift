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
