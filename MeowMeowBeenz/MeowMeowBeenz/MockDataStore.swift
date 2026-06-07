import Foundation

struct AppMockData: Codable {
    let cats: [CatProfile]
    let events: [TimelineEvent]
}

enum MockDataStore {
    private struct MockDataFile: Codable {
        let app: AppMockData?
    }

    static func load() -> AppMockData? {
        guard let url = Bundle.main.url(forResource: "mockData", withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let decoded = try? JSONDecoder().decode(MockDataFile.self, from: data) else {
            return nil
        }
        return decoded.app
    }

    static func report(for events: [TimelineEvent], range: ReportRange) -> HealthReport {
        let scoped = scopedEvents(events, range: range)
        let counts = EventCounts(
            eating: scoped.count { $0.behaviorLabel.contains("eating") || $0.behaviorLabel.contains("nutrition") },
            litter: scoped.count { $0.behaviorLabel.contains("litter") },
            active: scoped.count { event in
                let label = event.behaviorLabel
                return !label.contains("inactive") && (label.contains("active") || label.contains("play") || label.contains("walking"))
            },
            resting: scoped.count { event in
                let label = event.behaviorLabel
                return label.contains("inactive") || label.contains("resting") || label.contains("lying")
            },
            grooming: scoped.count { event in
                let label = event.behaviorLabel
                return label.contains("grooming") || label.contains("scratching") || label.contains("shake")
            },
            vocal: scoped.count { event in
                ["meow", "yowl", "chirp", "caterwaul"].contains { event.soundType.contains($0) }
            },
            review: scoped.count { $0.riskLevel == "review" }
        )
        let alerts = buildAlerts(from: scoped, counts: counts)
        let overall = alerts.contains { $0.level == "review" } ? "review" : (alerts.isEmpty ? "normal" : "watch")
        return HealthReport(
            dateLabel: label(for: range),
            range: range.rawValue,
            totalEvents: scoped.count,
            counts: counts,
            alerts: alerts,
            overall: overall,
            summary: summary(for: overall, events: scoped)
        )
    }

    private static func scopedEvents(_ events: [TimelineEvent], range: ReportRange) -> [TimelineEvent] {
        guard let latest = events.compactMap({ Format.date($0.time) }).max() else { return events }
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(secondsFromGMT: 0) ?? .current
        let dayStart = calendar.startOfDay(for: latest)
        let start: Date
        switch range {
        case .day:
            start = dayStart
        case .week:
            start = calendar.date(byAdding: .day, value: -6, to: dayStart) ?? dayStart
        case .month:
            start = calendar.date(byAdding: .day, value: -29, to: dayStart) ?? dayStart
        }
        return events.filter { event in
            guard let date = Format.date(event.time) else { return false }
            return date >= start && date <= latest
        }
    }

    private static func buildAlerts(from events: [TimelineEvent], counts: EventCounts) -> [Alert] {
        var alerts: [Alert] = []
        let risky = events.filter { $0.riskLevel == "watch" || $0.riskLevel == "review" }
        for event in risky.prefix(4) {
            let isReview = event.riskLevel == "review"
            alerts.append(
                Alert(
                    signal: "\(event.id)_alert",
                    level: event.riskLevel,
                    title: isReview ? "Possible discomfort" : "Behavior change",
                    evidence: ["\(event.catName ?? "Cat"): \(event.state) - \(event.summary)"],
                    suggestion: event.suggestion,
                    confidence: event.confidence
                )
            )
        }
        if counts.grooming >= 2 {
            alerts.append(
                Alert(
                    signal: "focused_grooming_pattern",
                    level: "watch",
                    title: "Focused grooming pattern",
                    evidence: ["Focused grooming or scratching appeared \(counts.grooming) times in this range."],
                    suggestion: "Inspect coat and skin, then watch whether the same spot keeps drawing attention.",
                    confidence: 0.66
                )
            )
        }
        return alerts
    }

    private static func summary(for overall: String, events: [TimelineEvent]) -> String {
        if events.isEmpty {
            return "No observations have been logged for this range."
        }
        if overall == "review" {
            return "A few observations deserve human review, especially nighttime vocalization or discomfort patterns."
        }
        if overall == "watch" {
            return "Most behavior is routine, with a few changes worth monitoring for repeats."
        }
        return "Observed behavior looks consistent with the normal household baseline."
    }

    private static func label(for range: ReportRange) -> String {
        switch range {
        case .day: return "Today"
        case .week: return "Last 7 days"
        case .month: return "Last 30 days"
        }
    }
}
