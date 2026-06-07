import SwiftUI

struct HomeView: View {
    @Environment(AppModel.self) private var app
    @State private var showingAccount = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 14) {
                    HouseholdAlertPanel()

                    if !app.apiReachable && !app.usesMockData {
                        SoftCard(
                            title: "Backend",
                            subtitle: "Connection status",
                            icon: "wifi.exclamationmark",
                            accent: .orange
                        ) {
                            HStack {
                                Label("Backend not reachable", systemImage: "wifi.exclamationmark")
                                Spacer()
                                SoftChip(text: "Needs attention", tone: .orange)
                            }
                            Text("Start the API server, then pull to refresh.")
                                .font(.footnote)
                                .foregroundStyle(.secondary)
                        }
                    }

                    CatSelector()

                    SoftCard(
                        title: "Selected cat",
                        subtitle: "\(app.selectedCat?.name ?? "Selected cat") health snapshot",
                        icon: "heart.text.square",
                        accent: .mint
                    ) {
                        LabeledContent("Overall status") { RiskBadge(level: app.overallLevel) }
                        if let report = app.report {
                            Text(report.summary)
                                .font(.subheadline)
                            Divider()
                            HStack(spacing: 12) {
                                SoftChip(text: "Observations · \(report.totalEvents)", tone: .blue)
                                SoftChip(text: "Vocal · \(report.counts.vocal)", tone: .purple)
                            }
                        } else {
                            Text("No report yet.")
                                .foregroundStyle(.secondary)
                        }
                    }

                    SoftCard(
                        title: "Cats",
                        subtitle: app.isSignedIn ? "Your tracked companions" : "Sign in to track your cats",
                        icon: "cat",
                        accent: .pink
                    ) {
                        if app.isSignedIn {
                            if app.cats.isEmpty {
                                Text("No cats yet — add one from your account.")
                                    .foregroundStyle(.secondary)
                            } else {
                                VStack(spacing: 8) {
                                    ForEach(app.cats) { cat in
                                        CatRow(cat: cat)
                                    }
                                }
                            }
                        } else {
                            Button("Sign in to add your cats") { showingAccount = true }
                                .buttonStyle(.borderedProminent)
                        }
                    }

                    if let latest = app.latestEvent {
                        SoftCard(
                            title: "Last heard",
                            subtitle: "Most recent event",
                            icon: "waveform",
                            accent: .teal
                        ) {
                            HStack {
                                Text(latest.state)
                                    .font(.body.weight(.semibold))
                                Spacer()
                                Text(Format.clock(latest.time))
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                            Text(Format.humanize(latest.intent))
                                .font(.footnote)
                                .foregroundStyle(.secondary)
                            Divider()
                            HStack {
                                Text("Confidence")
                                Spacer()
                                Text(Format.percent(latest.confidence))
                                    .fontWeight(.semibold)
                            }
                        }
                    }
                }
                .padding(16)
            }
            .background(AppBackdrop())
            .navigationTitle("Home")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { showingAccount = true } label: {
                        Image(systemName: app.isSignedIn ? "person.crop.circle.fill" : "person.crop.circle")
                    }
                }
            }
            .refreshable { await app.bootstrap() }
            .sheet(isPresented: $showingAccount) { AccountView() }
        }
    }
}

private struct HouseholdAlertPanel: View {
    @Environment(AppModel.self) private var app

    private var report: HealthReport? { app.householdReport ?? app.report }

    private var riskyEvents: [TimelineEvent] {
        let source = app.householdEvents.isEmpty ? app.events : app.householdEvents
        return source.filter { $0.riskLevel != "normal" }
    }

    private var alertCount: Int {
        if let report, !report.alerts.isEmpty {
            return min(report.alerts.count, 2)
        }
        return min(riskyEvents.count, 2)
    }

    private var catsAtRisk: [String] {
        Array(
            Set(riskyEvents.compactMap { event in
                let name = event.catName?.trimmingCharacters(in: .whitespacesAndNewlines)
                return name?.isEmpty == false ? name : nil
            })
        )
        .sorted()
    }

    private var headline: String {
        if app.isLoading {
            return "Checking the household"
        }
        switch Risk(app.householdOverallLevel) {
        case .review:
            return "Concerns to check"
        case .watch:
            return "Behavior concerns"
        case .normal:
            return "Demo concerns"
        }
    }

    private var subtitle: String {
        if app.isLoading {
            return "Pulling the latest demo observations"
        }
        if catsAtRisk.isEmpty {
            return "Load the demo day to show a couple of abnormal patterns"
        }
        return catsAtRisk.joined(separator: ", ")
    }

    var body: some View {
        SoftCard(
            title: headline,
            subtitle: subtitle,
            icon: "exclamationmark.triangle.fill",
            accent: Risk(app.householdOverallLevel).color
        ) {
            VStack(alignment: .leading, spacing: 12) {
                HStack(alignment: .center, spacing: 10) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("\(alertCount)")
                            .font(.system(size: 44, weight: .bold, design: .rounded))
                            .foregroundStyle(Risk(app.householdOverallLevel).color)
                        Text(alertCount == 1 ? "concern" : "concerns")
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    SoftChip(text: "Demo", tone: Risk(app.householdOverallLevel).color)
                }

                if let report {
                    Text(summaryText(for: report))
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                } else {
                    Text("The demo can show a night vocalization concern and a possible discomfort pattern without making the whole household feel critical.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }

                if let report, !report.alerts.isEmpty {
                    Divider()
                    VStack(spacing: 8) {
                        ForEach(report.alerts.prefix(2)) { alert in
                            HomeAlertRow(alert: alert)
                        }
                    }
                } else if !riskyEvents.isEmpty {
                    Divider()
                    VStack(spacing: 8) {
                        ForEach(riskyEvents.prefix(2)) { event in
                            RiskEventRow(event: event)
                        }
                    }
                }

                if report?.alerts.isEmpty != false && riskyEvents.isEmpty {
                    Divider()
                    VStack(spacing: 8) {
                        DemoConcernRow(
                            catName: "Luna",
                            title: "Night yowl while inactive",
                            detail: "High-intensity vocalization can be shown as a review case."
                        )
                        DemoConcernRow(
                            catName: "Saffron",
                            title: "Stiff movement and over-grooming",
                            detail: "Older-cat discomfort and repeated grooming can be shown as watch cases."
                        )
                    }
                }

                HStack(spacing: 8) {
                    SoftChip(text: "Observations · \(report?.totalEvents ?? app.householdEvents.count)", tone: .blue)
                    SoftChip(text: "Concerns · \(alertCount)", tone: .orange)
                }
            }
        }
    }

    private func summaryText(for report: HealthReport) -> String {
        if report.alerts.isEmpty {
            return "No major issues in this demo view."
        }
        return "A couple of patterns are worth checking in the demo timeline. This is a lightweight concern view, not an emergency screen."
    }
}

private struct HomeAlertRow: View {
    let alert: Alert

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack {
                Text(alert.title)
                    .font(.body.weight(.semibold))
                Spacer()
                RiskBadge(level: alert.level)
            }
            if let evidence = alert.evidence.first, !evidence.isEmpty {
                Text(evidence)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
            Text(alert.suggestion)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(10)
        .background(Color(.secondarySystemBackground).opacity(0.62), in: RoundedRectangle(cornerRadius: 12))
    }
}

private struct RiskEventRow: View {
    let event: TimelineEvent

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack {
                Text(event.catName ?? "Cat")
                    .font(.body.weight(.semibold))
                Spacer()
                RiskBadge(level: event.riskLevel)
            }
            Text(event.state)
                .font(.footnote.weight(.medium))
            Text(event.summary)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(10)
        .background(Color(.secondarySystemBackground).opacity(0.62), in: RoundedRectangle(cornerRadius: 12))
    }
}

private struct DemoConcernRow: View {
    let catName: String
    let title: String
    let detail: String

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack {
                Text(catName)
                    .font(.body.weight(.semibold))
                Spacer()
                SoftChip(text: "Demo", tone: .orange)
            }
            Text(title)
                .font(.footnote.weight(.medium))
            Text(detail)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(10)
        .background(Color(.secondarySystemBackground).opacity(0.62), in: RoundedRectangle(cornerRadius: 12))
    }
}

struct CatRow: View {
    let cat: CatProfile

    var body: some View {
        HStack(spacing: 12) {
            Text(cat.initials)
                .font(.headline)
                .frame(width: 40, height: 40)
                .background(Color(hex: cat.accent).opacity(0.25), in: Circle())
                .foregroundStyle(Color(hex: cat.accent))
            VStack(alignment: .leading) {
                Text(cat.name).font(.body.weight(.semibold))
                Text(cat.age).font(.caption).foregroundStyle(.secondary)
            }
            Spacer()
            Image(systemName: "chevron.right")
                .font(.caption.weight(.medium))
                .foregroundStyle(.tertiary)
        }
        .padding(10)
        .background(Color(.secondarySystemBackground).opacity(0.62), in: RoundedRectangle(cornerRadius: 12))
    }
}
