import SwiftUI

struct DataView: View {
    @Environment(AppModel.self) private var app

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 14) {
                    CatSelector()

                    SoftCard(
                        title: "Recent meows",
                        subtitle: "\(app.selectedCat?.name ?? "Selected cat") · \(app.events.count) events loaded",
                        icon: "waveform.path.ecg",
                        accent: .purple
                    ) {
                        if app.events.isEmpty {
                            VStack(alignment: .leading, spacing: 8) {
                                Label("No events yet", systemImage: "waveform")
                                    .foregroundStyle(.secondary)
                                Text("Run Analyze or load a demo day from the Upload tab.")
                                    .font(.footnote)
                                    .foregroundStyle(.secondary)
                            }
                        } else {
                            VStack(spacing: 10) {
                                ForEach(app.events) { event in
                                    EventRow(event: event)
                                }
                            }
                        }
                    }
                }
                .padding(16)
            }
            .background(AppBackdrop())
            .navigationTitle("Data")
            .refreshable { await app.loadTimelineAndReport() }
        }
    }
}

struct EventRow: View {
    let event: TimelineEvent

    var body: some View {
        let risk = Risk(event.riskLevel)
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(event.state)
                    .font(.body.weight(.semibold))
                Spacer()
                if event.riskLevel == "normal" {
                    SoftChip(text: "Low concern", tone: .green)
                } else {
                    RiskBadge(level: event.riskLevel)
                }
            }
            Text(event.summary)
                .font(.subheadline)
                .foregroundStyle(.secondary)
            HStack(spacing: 8) {
                if let catName = event.catName, !catName.isEmpty {
                    SoftChip(text: catName, tone: .pink)
                }
                SoftChip(text: Format.humanize(event.intent), tone: risk.color)
                SoftChip(text: Format.percent(event.confidence), tone: .blue)
            }
            Text(Format.relative(event.time))
                .font(.caption)
                .foregroundStyle(.secondary)
            if !event.suggestion.isEmpty {
                Divider()
                Text(event.suggestion)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(12)
        .background(Color(.secondarySystemBackground).opacity(0.65), in: RoundedRectangle(cornerRadius: 12))
    }
}
