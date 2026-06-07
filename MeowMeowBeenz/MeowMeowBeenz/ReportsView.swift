import SwiftUI

struct ReportsView: View {
    @Environment(AppModel.self) private var app

    private var rangeBinding: Binding<ReportRange> {
        Binding(
            get: { app.reportRange },
            set: { newValue in Task { await app.changeRange(newValue) } }
        )
    }

    var body: some View {
        NavigationStack {
            List {
                Section {
                    Picker("Range", selection: rangeBinding) {
                        ForEach(ReportRange.allCases) { range in
                            Text(range.label).tag(range)
                        }
                    }
                    .pickerStyle(.segmented)
                }

                if let report = app.report {
                    Section("Summary") {
                        LabeledContent("Overall") { RiskBadge(level: report.overall) }
                        LabeledContent("Window", value: report.dateLabel)
                        Text(report.summary).foregroundStyle(.secondary)
                    }

                    Section("Signals") {
                        if report.alerts.isEmpty {
                            Label("No distress signals detected", systemImage: "checkmark.seal")
                                .foregroundStyle(.green)
                        } else {
                            ForEach(report.alerts) { alert in
                                AlertRow(alert: alert)
                            }
                        }
                    }

                    Section("Counts") {
                        CountRow(label: "Eating", value: report.counts.eating)
                        CountRow(label: "Litter", value: report.counts.litter)
                        CountRow(label: "Active", value: report.counts.active)
                        CountRow(label: "Resting", value: report.counts.resting)
                        CountRow(label: "Grooming", value: report.counts.grooming)
                        CountRow(label: "Vocal", value: report.counts.vocal)
                    }
                } else {
                    ContentUnavailableView("No report", systemImage: "doc.text",
                                           description: Text("Pull to refresh once the backend is running."))
                }
            }
            .navigationTitle("Reports")
            .refreshable { await app.changeRange(app.reportRange) }
        }
    }
}

private struct AlertRow: View {
    let alert: Alert
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(alert.title).font(.body.weight(.semibold))
                Spacer()
                RiskBadge(level: alert.level)
            }
            if let evidence = alert.evidence.first {
                Text(evidence).font(.footnote).foregroundStyle(.secondary)
            }
            Text(alert.suggestion).font(.caption).foregroundStyle(.tertiary)
        }
        .padding(.vertical, 2)
    }
}

private struct CountRow: View {
    let label: String
    let value: Int
    var body: some View { LabeledContent(label, value: "\(value)") }
}
