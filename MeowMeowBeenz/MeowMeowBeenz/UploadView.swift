import SwiftUI

struct UploadView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var working = false

    var body: some View {
        NavigationStack {
            List {
                Section("Analyze") {
                    Button {
                        run { await app.analyzeNow() }
                    } label: {
                        Label("Analyze now", systemImage: "waveform.badge.magnifyingglass")
                    }
                    Button {
                        run { await app.loadDemoDay() }
                    } label: {
                        Label("Load demo day", systemImage: "calendar.badge.clock")
                    }
                }

                Section("Upload") {
                    Button { } label: { Label("Upload Video", systemImage: "video") }
                    Button { } label: { Label("Upload Audio", systemImage: "waveform") }
                    Text("Audio and video will be sent to the model to classify likely mood, need, or distress.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }

                if let latest = app.latestEvent {
                    Section("Latest result") {
                        LabeledContent("State", value: latest.state)
                        LabeledContent("Mood", value: Format.humanize(latest.intent))
                        LabeledContent("Confidence", value: Format.percent(latest.confidence))
                    }
                }
            }
            .navigationTitle("Upload")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { dismiss() }
                }
            }
            .overlay { if working { ProgressView() } }
        }
    }

    private func run(_ action: @escaping () async -> Void) {
        working = true
        Task {
            await action()
            working = false
        }
    }
}
