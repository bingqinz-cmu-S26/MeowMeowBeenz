import SwiftUI

struct DataView: View {
    @Environment(AppModel.self) private var app

    var body: some View {
        NavigationStack {
            List {
                if app.events.isEmpty {
                    ContentUnavailableView(
                        "No events yet",
                        systemImage: "waveform",
                        description: Text("Run Analyze or load a demo day from the Upload tab.")
                    )
                } else {
                    Section("Recent meows") {
                        ForEach(app.events) { event in
                            EventRow(event: event)
                        }
                    }
                }
            }
            .navigationTitle("Data")
            .refreshable { await app.loadTimelineAndReport() }
        }
    }
}

struct EventRow: View {
    let event: TimelineEvent
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(event.state).font(.body.weight(.semibold))
                Spacer()
                if event.riskLevel != "normal" { RiskBadge(level: event.riskLevel) }
            }
            Text(event.summary)
                .font(.footnote)
                .foregroundStyle(.secondary)
            HStack(spacing: 6) {
                Text(Format.humanize(event.intent))
                Text("·")
                Text(Format.percent(event.confidence))
                Text("·")
                Text(Format.relative(event.time))
            }
            .font(.caption)
            .foregroundStyle(.tertiary)
        }
        .padding(.vertical, 2)
    }
}
