import SwiftUI

struct ReportsView: View {
    @Environment(AppModel.self) private var app

    private var rangeBinding: Binding<ReportRange> {
        Binding(
            get: { app.reportRange },
            set: { newValue in Task { await app.changeRange(newValue) } }
        )
    }

    private let countGrid = [
        GridItem(.flexible(), spacing: 10),
        GridItem(.flexible(), spacing: 10)
    ]

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 14) {
                    CatSelector()

                    SoftCard(
                        title: "Range",
                        subtitle: "\(app.selectedCat?.name ?? "Selected cat") reporting window",
                        icon: "calendar",
                        accent: .indigo
                    ) {
                        Picker("Range", selection: rangeBinding) {
                            ForEach(ReportRange.allCases) { range in
                                Text(range.label).tag(range)
                            }
                        }
                        .pickerStyle(.segmented)
                    }

                    if let report = app.report {
                        SoftCard(
                            title: "Summary",
                            subtitle: report.dateLabel,
                            icon: "chart.bar.doc.horizontal",
                            accent: .mint
                        ) {
                            HStack {
                                Text("Overall")
                                Spacer()
                                RiskBadge(level: report.overall)
                            }
                            .font(.body.weight(.semibold))

                            Text(report.summary)
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                        }

                        SoftCard(
                            title: "Signals",
                            subtitle: "\(report.alerts.count) issue\(report.alerts.count == 1 ? "" : "s")",
                            icon: "bell.badge",
                            accent: .orange
                        ) {
                            if report.alerts.isEmpty {
                                HStack(spacing: 6) {
                                    Label("No distress signals detected", systemImage: "checkmark.seal.fill")
                                        .foregroundStyle(.green)
                                    Spacer()
                                }
                            } else {
                                VStack(spacing: 10) {
                                    ForEach(report.alerts) { alert in
                                        AlertRow(alert: alert)
                                    }
                                }
                            }
                        }

                        SoftCard(
                            title: "Activity counts",
                            subtitle: report.dateLabel,
                            icon: "chart.pie",
                            accent: .blue
                        ) {
                            let countItems: [(String, Int, Color)] = [
                                ("Eating", report.counts.eating, .orange),
                                ("Litter", report.counts.litter, .brown),
                                ("Active", report.counts.active, .green),
                                ("Resting", report.counts.resting, .gray),
                                ("Grooming", report.counts.grooming, .teal),
                                ("Vocal", report.counts.vocal, .purple)
                            ]

                            LazyVGrid(columns: countGrid, spacing: 10) {
                                ForEach(countItems, id: \.0) { item in
                                    CountTile(
                                        label: item.0,
                                        value: item.1,
                                        tone: item.2
                                    )
                                }
                            }
                        }
                    } else {
                        SoftCard(
                            title: "No report",
                            subtitle: "Pull to refresh once backend is reachable",
                            icon: "doc.text",
                            accent: .blue
                        ) {
                            Text("Refresh or switch range after the backend is running.")
                                .font(.footnote)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
                .padding(16)
            }
            .background(AppBackdrop())
            .navigationTitle("Reports")
            .refreshable { await app.changeRange(app.reportRange) }
        }
    }
}

private struct AlertRow: View {
    let alert: Alert

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(alert.title).font(.body.weight(.semibold))
                Spacer()
                RiskBadge(level: alert.level)
            }
            if let evidence = alert.evidence.first {
                Text(evidence)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
            Text(alert.suggestion)
                .font(.caption)
                .foregroundStyle(.tertiary)
            Text("Confidence \(Format.percent(alert.confidence))")
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
        .padding(12)
        .background(Color(.secondarySystemBackground).opacity(0.6), in: RoundedRectangle(cornerRadius: 12))
    }
}

private struct CountTile: View {
    let label: String
    let value: Int
    let tone: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label)
                .font(.caption)
                .foregroundStyle(.secondary)
            Text("\(value)")
                .font(.title2.weight(.bold))
                .foregroundStyle(tone)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(10)
        .background(tone.opacity(0.12), in: RoundedRectangle(cornerRadius: 12))
    }
}
