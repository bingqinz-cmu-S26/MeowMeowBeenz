import Foundation
import UniformTypeIdentifiers
import Observation

/// Central observable app state. All UI reads from here; networking goes through APIClient.
@MainActor
@Observable
final class AppModel {
    // Configuration (persisted)
    var baseURLString: String {
        didSet { UserDefaults.standard.set(baseURLString, forKey: "baseURL") }
    }
    var token: String? {
        didSet { UserDefaults.standard.set(token, forKey: "token") }
    }

    // Session
    var user: AuthUser?

    // Data
    var cats: [CatProfile] = []
    var events: [TimelineEvent] = []
    var report: HealthReport?
    var reportRange: ReportRange = .day

    // Chat
    var chat: [ChatMessage] = [
        ChatMessage(role: .assistant,
                    text: "Ask about recent meows, mood trends, or whether a pattern is worth watching.",
                    provider: "local")
    ]
    var isSending = false

    // Status
    var apiReachable = false
    var isLoading = false
    var errorMessage: String?

    var isSignedIn: Bool { token != nil && user != nil }

    private var client: APIClient {
        APIClient(baseURL: URL(string: baseURLString) ?? URL(string: "http://localhost:8000")!, token: token)
    }

    init() {
        self.baseURLString = UserDefaults.standard.string(forKey: "baseURL") ?? "http://localhost:8000"
        self.token = UserDefaults.standard.string(forKey: "token")
    }

    // MARK: Lifecycle

    func bootstrap() async {
        isLoading = true
        defer { isLoading = false }
        apiReachable = (try? await client.health()) ?? false
        await loadTimelineAndReport()
        if token != nil {
            await restoreSession()
        }
    }

    func loadTimelineAndReport() async {
        async let events = try? client.events()
        async let report = try? client.report(range: reportRange)
        self.events = await events ?? []
        self.report = await report
    }

    func changeRange(_ range: ReportRange) async {
        reportRange = range
        report = try? await client.report(range: range)
    }

    // MARK: Auth

    func restoreSession() async {
        do {
            user = try await client.me()
            cats = (try? await client.cats()) ?? []
        } catch {
            // Token invalid/expired — clear it silently.
            token = nil
            user = nil
        }
    }

    func signIn(username: String, password: String, isRegister: Bool) async {
        errorMessage = nil
        do {
            let auth = isRegister
                ? try await client.register(username: username, password: password, displayName: nil)
                : try await client.login(username: username, password: password)
            token = auth.token
            user = auth.user
            cats = (try? await client.cats()) ?? []
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func signOut() {
        token = nil
        user = nil
        cats = []
    }

    func addCat(name: String, birthDate: String, device: String?) async -> Bool {
        do {
            let cat = try await client.createCat(name: name, birthDate: birthDate, device: device)
            cats.append(cat)
            return true
        } catch {
            errorMessage = error.localizedDescription
            return false
        }
    }

    // MARK: Live controls

    func analyzeNow() async {
        if let event = try? await client.addScenario("live") {
            events.insert(event, at: 0)
            report = try? await client.report(range: reportRange)
        }
    }

    func loadDemoDay() async {
        if let seeded = try? await client.seedEvents() {
            events = seeded
            report = try? await client.report(range: reportRange)
        }
    }

    func injectScenario(_ type: String) async {
        if let event = try? await client.addScenario(type) {
            events.insert(event, at: 0)
            report = try? await client.report(range: reportRange)
        }
    }

    // MARK: Chat

    func sendMessage(_ question: String) async {
        let trimmed = question.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        chat.append(ChatMessage(role: .owner, text: trimmed))
        isSending = true
        defer { isSending = false }
        do {
            let answer = try await client.ask(question: trimmed, timeline: events, report: report)
            chat.append(ChatMessage(role: .assistant, text: answer.answer, provider: answer.provider))
        } catch {
            chat.append(ChatMessage(role: .assistant,
                                    text: "I couldn't reach the assistant. Check that the backend is running.",
                                    provider: "error"))
        }
    }

    // MARK: Voice

    func livekitToken() async throws -> LiveKitToken {
        let room = "voice-\(UUID().uuidString.lowercased())"
        return try await client.livekitToken(room: room)
    }

    // MARK: Clip upload

    func analyzeUploadedVideo(fileData: Data, filename: String, mimeType: String) async -> ClipAnalysisResponse? {
        do {
            let result = try await client.analyzeClip(fileData: fileData, filename: filename, mimeType: mimeType)
            guard result.ok else {
                errorMessage = result.text
                return nil
            }
            if let event = result.event ?? result.analysis {
                events.insert(event, at: 0)
                report = try? await client.report(range: reportRange)
            }
            errorMessage = nil
            return result
        } catch {
            errorMessage = error.localizedDescription
            return nil
        }
    }

    func mimeType(for url: URL) -> String {
        let ext = url.pathExtension.lowercased()
        guard let type = UTType(filenameExtension: ext) else {
            return "video/mp4"
        }
        return type.preferredMIMEType ?? "video/\(ext)"
    }

    // MARK: Derived

    var latestEvent: TimelineEvent? { events.first }

    var overallLevel: String { report?.overall ?? "normal" }
}
