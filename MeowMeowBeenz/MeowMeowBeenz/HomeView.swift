import SwiftUI

struct HomeView: View {
    @Environment(AppModel.self) private var app
    @State private var showingAccount = false

    var body: some View {
        NavigationStack {
            List {
                if !app.apiReachable {
                    Section {
                        Label("Backend not reachable", systemImage: "wifi.exclamationmark")
                            .foregroundStyle(.secondary)
                        Text("Start the API server, then pull to refresh.")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                }

                Section("Today") {
                    LabeledContent("Status") { RiskBadge(level: app.overallLevel) }
                    if let report = app.report {
                        Text(report.summary)
                            .foregroundStyle(.secondary)
                        LabeledContent("Observations", value: "\(report.totalEvents)")
                        LabeledContent("Vocal events", value: "\(report.counts.vocal)")
                    } else {
                        Text("No report yet.").foregroundStyle(.secondary)
                    }
                }

                Section("Cats") {
                    if app.isSignedIn {
                        if app.cats.isEmpty {
                            Text("No cats yet — add one from your account.")
                                .foregroundStyle(.secondary)
                        } else {
                            ForEach(app.cats) { cat in
                                CatRow(cat: cat)
                            }
                        }
                    } else {
                        Button("Sign in to add your cats") { showingAccount = true }
                    }
                }

                if let latest = app.latestEvent {
                    Section("Last heard") {
                        LabeledContent(latest.state, value: Format.clock(latest.time))
                        LabeledContent("Interpreted as", value: Format.humanize(latest.intent))
                        LabeledContent("Confidence", value: Format.percent(latest.confidence))
                    }
                }
            }
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
        }
    }
}

// Hex color helper for the per-cat accent strings from the backend.
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
