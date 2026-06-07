import SwiftUI

struct HomeView: View {
    @Environment(AppModel.self) private var app
    @State private var showingAccount = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 14) {
                    if !app.apiReachable {
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

                    SoftCard(
                        title: "Today",
                        subtitle: "Health snapshot",
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
