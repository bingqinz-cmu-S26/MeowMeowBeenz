import SwiftUI

struct VoiceView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var voice = VoiceChatModel()

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 18) {
                    hero

                    SoftCard(title: "Conversation", subtitle: "Owner view", icon: "dot.radiowaves.left.and.right", accent: .indigo) {
                        StatusRow(
                            icon: "mic.fill",
                            tone: .blue,
                            title: "Your question",
                            active: voice.isUserSpeaking,
                            activeLabel: "Speaking…",
                            idleLabel: voice.phase == .connected ? "Waiting for you" : "—",
                            transcript: voice.userTranscript,
                            placeholder: voice.phase == .connected ? "Ask about a cat, a time of day, or a health signal." : "Start a conversation to talk with Beenz."
                        )
                        Divider()
                        StatusRow(
                            icon: "cat.fill",
                            tone: .pink,
                            title: "Beenz answer",
                            active: voice.isThinking || voice.isAgentSpeaking || voice.isAgentUsingContext,
                            activeLabel: beenzStatusLabel,
                            idleLabel: voice.phase == .connected ? "Listening" : "—",
                            transcript: voice.agentTranscript,
                            placeholder: voice.phase == .connected ? "A clear answer will appear here." : "Beenz will answer here once connected.",
                            contextActive: voice.isAgentUsingContext
                        )
                    }

                    if let error = voice.errorMessage {
                        SoftCard(title: "Problem", icon: "exclamationmark.triangle", accent: .orange) {
                            Text(error).font(.footnote).foregroundStyle(.red)
                        }
                    }
                }
                .padding(16)
            }
            .background(AppBackdrop())
            .navigationTitle("Voice")
            .navigationBarTitleDisplayMode(.inline)
            .safeAreaInset(edge: .bottom) { actionBar }
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { Task { await voice.stop(); dismiss() } }
                }
            }
            .onDisappear { Task { await voice.stop() } }
        }
    }

    private var hero: some View {
        VStack(spacing: 12) {
            Image(systemName: heroSymbol)
                .font(.system(size: 76))
                .foregroundStyle(heroTint)
                .symbolEffect(.variableColor.iterative, isActive: voice.isUserSpeaking || voice.isAgentSpeaking || voice.isThinking)
                .frame(height: 110)
            SoftChip(text: voice.statusText, tone: heroTint)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 12)
    }

    private var actionBar: some View {
        Button(action: toggle) {
            Text(voice.isActive ? "End conversation" : "Start conversation")
                .frame(maxWidth: .infinity)
        }
        .buttonStyle(.borderedProminent)
        .controlSize(.large)
        .tint(voice.isActive ? .red : .accentColor)
        .disabled(voice.phase == .connecting)
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(.ultraThinMaterial)
    }

    private var heroSymbol: String {
        switch voice.phase {
        case .idle: return "mic.circle"
        case .connecting: return "waveform.circle"
        case .failed: return "exclamationmark.triangle"
        case .connected:
            if voice.isUserSpeaking { return "mic.fill" }
            if voice.isThinking { return "ellipsis.bubble" }
            if voice.isAgentSpeaking { return "waveform" }
            return "ear"
        }
    }

    private var heroTint: Color {
        switch voice.phase {
        case .failed: return .red
        case .connected: return voice.isUserSpeaking ? .blue : (voice.isThinking || voice.isAgentSpeaking ? .pink : .mint)
        default: return .secondary
        }
    }

    private var beenzStatusLabel: String {
        if voice.isAgentUsingContext { return "Checking records" }
        if voice.isThinking { return "Thinking…" }
        return "Speaking…"
    }

    private func toggle() {
        Task {
            if voice.isActive {
                await voice.stop()
            } else {
                do {
                    let token = try await app.livekitToken()
                    await voice.connect(url: token.url, token: token.token, configured: token.configured)
                } catch {
                    await voice.fail(with: error.localizedDescription)
                }
            }
        }
    }
}

private struct StatusRow: View {
    let icon: String
    let tone: Color
    let title: String
    let active: Bool
    let activeLabel: String
    let idleLabel: String
    let transcript: String
    let placeholder: String
    var contextActive = false

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 10) {
                Image(systemName: icon)
                    .foregroundStyle(active ? tone : .secondary)
                    .frame(width: 22)
                Text(title).font(.body.weight(.semibold))
                Spacer()
                SoftChip(text: active ? activeLabel : idleLabel, tone: active ? tone : .gray)
            }
            if contextActive {
                HStack(spacing: 8) {
                    ProgressView()
                        .controlSize(.small)
                    Text("Looking through the recent activity timeline.")
                        .font(.footnote.weight(.medium))
                }
                .foregroundStyle(tone)
                .padding(.leading, 32)
            }

            if !transcript.isEmpty {
                Text(transcript)
                    .font(title == "Beenz answer" ? .body.weight(.medium) : .callout)
                    .lineSpacing(3)
                    .foregroundStyle(title == "Beenz answer" ? .primary : .secondary)
                    .padding(.leading, 32)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .fixedSize(horizontal: false, vertical: true)
            } else if !contextActive {
                Text(placeholder)
                    .font(.footnote)
                    .foregroundStyle(.tertiary)
                    .padding(.leading, 32)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .padding(.vertical, 2)
    }
}
