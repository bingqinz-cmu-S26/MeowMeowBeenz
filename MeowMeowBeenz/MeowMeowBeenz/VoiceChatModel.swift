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
        guard phase != .connecting, phase != .connected else { return }
        errorMessage = nil
        guard configured, !url.isEmpty, !token.isEmpty else {
            phase = .failed
            errorMessage = "Voice isn't configured on the server (set LIVEKIT_* and run voice_agent.py)."
            return
        }
        phase = .connecting
        do {
            let room = Room()
            let observer = RoomObserver(model: self)
            room.add(delegate: observer)
            self.room = room
            self.observer = observer
            try await room.connect(url: url, token: token)
            try await room.localParticipant.setMicrophone(enabled: true)
            phase = .connected
        } catch {
            errorMessage = error.localizedDescription
            await teardown()
            phase = .failed
        }
    }

    func stop() async {
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
        if let room { await room.disconnect() }
        room = nil
        observer = nil
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

    fileprivate func applyConnection(_ state: ConnectionState) {
        if state == .disconnected, phase == .connected {
            reset()
            phase = .idle
        }
    }
}

/// Plain (non-isolated) NSObject delegate. Extracts Sendable values on the SDK's
/// thread, then hops to the main actor to update the observable model.
private final class RoomObserver: NSObject, RoomDelegate {
    nonisolated(unsafe) weak var model: VoiceChatModel?

    init(model: VoiceChatModel) {
        self.model = model
        super.init()
    }

    func room(_ room: Room, didUpdateSpeakingParticipants participants: [Participant]) {
        let user = participants.contains { $0 is LocalParticipant }
        let agent = participants.contains { $0.isAgent }
        let model = self.model
        Task { @MainActor in model?.applySpeaking(user: user, agent: agent) }
    }

    func room(_ room: Room, participant: Participant, didUpdateAttributes attributes: [String: String]) {
        guard participant.isAgent else { return }
        let state = participant.agentState
        let model = self.model
        Task { @MainActor in model?.applyAgentState(state) }
    }

    func room(_ room: Room,
              participant: Participant,
              trackPublication: TrackPublication,
              didReceiveTranscriptionSegments segments: [TranscriptionSegment]) {
        let fromAgent = participant.isAgent
        let text = segments.map(\.text).joined(separator: " ")
        guard !text.isEmpty else { return }
        let model = self.model
        Task { @MainActor in model?.applyTranscript(text, fromAgent: fromAgent) }
    }

    func room(_ room: Room, didUpdateConnectionState connectionState: ConnectionState, from oldConnectionState: ConnectionState) {
        let model = self.model
        Task { @MainActor in model?.applyConnection(connectionState) }
    }
}
