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
        if fromAgent { agentTranscript = text } else { userTranscript = text }
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
