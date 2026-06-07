import Foundation
import LiveKit

/// Drives a hands-free voice session: joins the LiveKit room that the backend
/// voice_agent.py worker is in, publishes the mic, and surfaces live status —
/// you speaking, your words transcribed, the agent thinking, and the agent speaking.
@MainActor
@Observable
final class VoiceChatModel {
    enum Phase { case idle, connecting, connected, failed }

    var phase: Phase = .idle
    var errorMessage: String?

    // Live conversation status (updated from the room delegate).
    private(set) var agentState: AgentState = .idle
    private(set) var isUserSpeaking = false
    private(set) var isAgentSpeaking = false
    private(set) var isAgentUsingContext = false
    private(set) var userTranscript = ""
    private(set) var agentTranscript = ""

    private var room: Room?
    private var observer: RoomObserver?
    private var connectTask: Task<Void, Never>?
    private var sessionOperation: Task<Void, Never>?
    private var activeSessionID = UUID()

    fileprivate func isActiveSession(_ id: UUID) -> Bool {
        activeSessionID == id
    }

    /// Serialize connect/stop so End always finishes cleanup before the next Start.
    private func runSessionOperation(_ operation: @escaping @MainActor () async -> Void) async {
        let previous = sessionOperation
        let task = Task { @MainActor in
            if let previous { await previous.value }
            await operation()
        }
        sessionOperation = task
        await task.value
    }

    var isActive: Bool { phase == .connecting || phase == .connected }
    var isThinking: Bool { phase == .connected && agentState == .thinking }

    /// One human-readable line describing what's happening right now.
    var statusText: String {
        switch phase {
        case .idle: return "Tap to start talking with Beenz"
        case .connecting: return "Connecting…"
        case .failed: return "Couldn't connect"
        case .connected:
            if isUserSpeaking { return "Listening to you…" }
            switch agentState {
            case .thinking: return "Beenz is thinking…"
            case .speaking: return "Beenz is speaking…"
            case .listening: return "Listening — just talk"
            case .initializing: return "Warming up…"
            case .idle: return "Connected"
            }
        }
    }

    func connect(url: String, token: String, configured: Bool) async {
        await runSessionOperation {
            await self.connectSession(url: url, token: token, configured: configured)
        }
    }

    private func connectSession(url: String, token: String, configured: Bool) async {
        guard phase != .connecting, phase != .connected else { return }
        errorMessage = nil
        guard configured, !url.isEmpty, !token.isEmpty else {
            phase = .failed
            errorMessage = "Voice isn't configured on the server (set LIVEKIT_* and run voice_agent.py)."
            return
        }

        connectTask?.cancel()
        await teardown()

        let sessionID = UUID()
        activeSessionID = sessionID
        phase = .connecting

        let task = Task { @MainActor in
            do {
                AudioManager.prepare()
                let room = Room()
                let observer = RoomObserver(model: self, sessionID: sessionID)
                room.add(delegate: observer)
                self.room = room
                self.observer = observer

                try await withThrowingTaskGroup(of: Void.self) { group in
                    group.addTask {
                        try await Task.sleep(for: .seconds(20))
                        throw VoiceConnectTimeout()
                    }
                    group.addTask {
                        try Task.checkCancellation()
                        try await room.withPreConnectAudio {
                            try Task.checkCancellation()
                            try await room.connect(url: url, token: token)
                        }
                        try Task.checkCancellation()
                        try await room.localParticipant.setMicrophone(enabled: true)
                    }
                    try await group.next()
                    group.cancelAll()
                }

                guard !Task.isCancelled, self.isActiveSession(sessionID) else {
                    await self.teardown()
                    return
                }
                self.phase = .connected
            } catch is VoiceConnectTimeout {
                guard self.isActiveSession(sessionID) else { return }
                self.errorMessage = "Connection timed out. Check that ./run.sh is running and try again."
                await self.teardown()
                self.phase = .failed
            } catch is CancellationError {
                await self.teardown()
                if self.isActiveSession(sessionID) {
                    self.phase = .idle
                }
            } catch {
                guard self.isActiveSession(sessionID) else { return }
                self.errorMessage = error.localizedDescription
                await self.teardown()
                self.phase = .failed
            }
        }

        connectTask = task
        await task.value
        connectTask = nil
    }

    func stop() async {
        await runSessionOperation {
            await self.stopSession()
        }
    }

    private func stopSession() async {
        connectTask?.cancel()
        connectTask = nil
        activeSessionID = UUID()
        await teardown()
        reset()
        phase = .idle
        errorMessage = nil
    }

    func fail(with message: String) async {
        reset()
        phase = .failed
        errorMessage = message
    }

    private func reset() {
        agentState = .idle
        isUserSpeaking = false
        isAgentSpeaking = false
        isAgentUsingContext = false
        userTranscript = ""
        agentTranscript = ""
    }

    private func teardown() async {
        guard let room else { return }
        if let observer {
            room.remove(delegate: observer)
        }
        await room.localParticipant.unpublishAll()
        do {
            try await room.localParticipant.setMicrophone(enabled: false)
        } catch {
            // Best-effort cleanup before disconnect.
        }
        await room.disconnect()
        self.room = nil
        self.observer = nil
    }

    // MARK: - Applied from RoomObserver (already hopped to the main actor)

    fileprivate func applySpeaking(user: Bool, agent: Bool) {
        isUserSpeaking = user
        isAgentSpeaking = agent
    }

    fileprivate func applyAgentState(_ state: AgentState) {
        agentState = state
    }

    fileprivate func applyTranscript(_ text: String, fromAgent: Bool) {
        if fromAgent {
            let display = VoiceTranscriptFormatter.agentDisplayText(from: text)
            isAgentUsingContext = display.isUsingContext && display.text.isEmpty
            if !display.text.isEmpty {
                agentTranscript = display.text
            }
        } else {
            let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
            let previous = userTranscript.trimmingCharacters(in: .whitespacesAndNewlines)
            if !trimmed.isEmpty, trimmed != previous {
                agentTranscript = ""
                isAgentUsingContext = false
            }
            userTranscript = text
        }
    }

    fileprivate func applyConnection(_ state: ConnectionState, sessionID: UUID) {
        guard isActiveSession(sessionID) else { return }
        if state == .disconnected, phase == .connected {
            reset()
            phase = .idle
        }
    }
}

private struct VoiceConnectTimeout: Error {}

private struct AgentDisplayText {
    let text: String
    let isUsingContext: Bool
}

private enum VoiceTranscriptFormatter {
    static func agentDisplayText(from rawText: String) -> AgentDisplayText {
        let isUsingContext = rawText.localizedCaseInsensitiveContains("lookup_cat_activity")
            || rawText.localizedCaseInsensitiveContains("<tool_call")

        var text = rawText
        text = replace(pattern: #"(?s)<tool_call>.*?</tool_call>"#, in: text)
        text = replace(pattern: #"(?s)<tool_call>.*"#, in: text)
        text = replace(pattern: #"(?s)\{\s*"name"\s*:\s*"lookup_cat_activity".*?\}\s*"#, in: text)
        text = replace(pattern: #"(?s)\{\s*"time_of_day".*?\}\s*"#, in: text)
        text = replace(pattern: #"(?s)\*[^*]{0,160}\*"#, in: text)
        text = replace(pattern: #"```(?:json)?|```"#, in: text)
        text = replace(pattern: #"\s+"#, in: text, with: " ")
            .trimmingCharacters(in: .whitespacesAndNewlines)

        let ownerFacing = filteredOwnerFacingSentences(from: text)
        let displayText = ownerFacing.isEmpty ? fallbackText(for: rawText) : ownerFacing
        return AgentDisplayText(text: displayText, isUsingContext: isUsingContext)
    }

    private static func filteredOwnerFacingSentences(from text: String) -> String {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return "" }

        let rawSentences = trimmed
            .split(whereSeparator: { ".!?".contains($0) })
            .map { String($0).trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }

        guard !rawSentences.isEmpty else { return trimmed }

        var seen = Set<String>()
        let sentences = rawSentences.compactMap { sentence -> String? in
            let lower = sentence.lowercased()
            let isInternalStep = [
                "let me check",
                "let me see",
                "let me look",
                "i'll check",
                "i will check",
                "i'm checking",
                "i am checking",
                "check on ",
                "looking up",
                "activity log",
                "activity timeline",
                "tool_call",
                "lookup_cat_activity",
                "arguments",
                "don't have the key",
                "do not have the key",
                "only know what you've told me",
                "only know what you have told me",
                "i don't have access",
                "i do not have access",
                "meow",
                "ears swivel",
                "tail flick"
            ].contains { lower.contains($0) }

            guard !isInternalStep else { return nil }
            guard !seen.contains(lower) else { return nil }
            seen.insert(lower)
            return sentence.hasSuffix(".") ? sentence : "\(sentence)."
        }

        return sentences.joined(separator: " ")
    }

    private static func fallbackText(for rawText: String) -> String {
        let lower = rawText.lowercased()
        if lower.contains("key") || lower.contains("access") {
            return "I can't read the activity timeline clearly right now. Try asking again with the cat's name and a time, like “What was Saffron doing this morning?”"
        }
        return "I didn't catch that clearly. Could you repeat it with the cat's name or the time you want me to check?"
    }

    private static func replace(pattern: String, in text: String, with replacement: String = " ") -> String {
        text.replacingOccurrences(
            of: pattern,
            with: replacement,
            options: [.regularExpression, .caseInsensitive]
        )
    }
}

/// Plain (non-isolated) NSObject delegate. Extracts Sendable values on the SDK's
/// thread, then hops to the main actor to update the observable model.
private final class RoomObserver: NSObject, RoomDelegate {
    nonisolated(unsafe) weak var model: VoiceChatModel?
    let sessionID: UUID

    init(model: VoiceChatModel, sessionID: UUID) {
        self.model = model
        self.sessionID = sessionID
        super.init()
    }

    func room(_ room: Room, didUpdateSpeakingParticipants participants: [Participant]) {
        let user = participants.contains { $0 is LocalParticipant }
        let agent = participants.contains { $0.isAgent }
        let model = self.model
        let sessionID = self.sessionID
        Task { @MainActor in
            guard model?.isActiveSession(sessionID) == true else { return }
            model?.applySpeaking(user: user, agent: agent)
        }
    }

    func room(_ room: Room, participant: Participant, didUpdateAttributes attributes: [String: String]) {
        guard participant.isAgent else { return }
        let state = participant.agentState
        let model = self.model
        let sessionID = self.sessionID
        Task { @MainActor in
            guard model?.isActiveSession(sessionID) == true else { return }
            model?.applyAgentState(state)
        }
    }

    func room(_ room: Room,
              participant: Participant,
              trackPublication: TrackPublication,
              didReceiveTranscriptionSegments segments: [TranscriptionSegment]) {
        let fromAgent = participant.isAgent
        let text = segments.map(\.text).joined(separator: " ")
        guard !text.isEmpty else { return }
        let model = self.model
        let sessionID = self.sessionID
        Task { @MainActor in
            guard model?.isActiveSession(sessionID) == true else { return }
            model?.applyTranscript(text, fromAgent: fromAgent)
        }
    }

    func room(_ room: Room, didUpdateConnectionState connectionState: ConnectionState, from oldConnectionState: ConnectionState) {
        let model = self.model
        let sessionID = self.sessionID
        Task { @MainActor in model?.applyConnection(connectionState, sessionID: sessionID) }
    }
}
