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
    var selectedCatId: String? {
        didSet { UserDefaults.standard.set(selectedCatId, forKey: "selectedCatId") }
    }
    var events: [TimelineEvent] = []
    var report: HealthReport?
    var householdEvents: [TimelineEvent] = []
    var householdReport: HealthReport?
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
    var mongodbStatus = "unknown"
    var isLoading = false
    var errorMessage: String?

    private let mockData = MockDataStore.load()
    let usesMockData = true

    var isSignedIn: Bool { token != nil && user != nil }

    private var client: APIClient {
        APIClient(baseURL: URL(string: baseURLString) ?? URL(string: "http://localhost:8000")!, token: token)
    }

    init() {
        self.baseURLString = UserDefaults.standard.string(forKey: "baseURL") ?? "http://localhost:8000"
        self.token = UserDefaults.standard.string(forKey: "token")
        self.selectedCatId = UserDefaults.standard.string(forKey: "selectedCatId")
    }

    // MARK: Lifecycle

    func bootstrap() async {
        isLoading = true
        defer { isLoading = false }
        await refreshAPIStatus()
        if token != nil {
            await restoreSession()
        }
        applyMockData(catId: selectedCatId, range: reportRange)
    }

    func refreshAPIStatus() async {
        do {
            let health = try await client.health()
            apiReachable = health.ok
            mongodbStatus = health.mongodb ?? "unknown"
            if mongodbStatus == "connected",
               errorMessage == "MongoDB is required for authentication." {
                errorMessage = nil
            }
        } catch {
            apiReachable = false
            mongodbStatus = "unreachable"
        }
    }

    func loadTimelineAndReport() async {
        applyMockData(catId: selectedCatId, range: reportRange)
    }

    func changeRange(_ range: ReportRange) async {
        reportRange = range
        applyMockReports(range: range)
    }

    func selectCat(_ catId: String) async {
        selectedCatId = catId
        await loadTimelineAndReport()
    }

    // MARK: Auth

    func restoreSession() async {
        do {
            user = try await client.me()
        } catch {
            // Token invalid/expired — clear it silently.
            token = nil
            user = nil
        }
        applyMockData(catId: selectedCatId, range: reportRange)
    }

    func signIn(username: String, password: String, isRegister: Bool) async {
        errorMessage = nil
        do {
            let auth = isRegister
                ? try await client.register(username: username, password: password, displayName: nil)
                : try await client.login(username: username, password: password)
            token = auth.token
            user = auth.user
            applyMockData(catId: selectedCatId, range: reportRange)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func signOut() {
        token = nil
        user = nil
        applyMockData(catId: selectedCatId, range: reportRange)
    }

    func addCat(name: String, birthDate: String, device: String?) async -> Bool {
        do {
            let cat = try await client.createCat(name: name, birthDate: birthDate, device: device)
            cats.append(cat)
            ensureSelectedCat()
            return true
        } catch {
            errorMessage = error.localizedDescription
            return false
        }
    }

    // MARK: Live controls

    func analyzeNow() async {
        if let event = try? await client.addScenario("live") {
            insertVisibleEvent(event)
            await refreshReports()
        }
    }

    func loadDemoDay() async {
        applyMockData(catId: selectedCatId, range: reportRange)
    }

    func injectScenario(_ type: String) async {
        if let event = try? await client.addScenario(type) {
            insertVisibleEvent(event)
            await refreshReports()
        }
    }

    // MARK: Chat

    func sendMessage(_ question: String) async {
        let trimmed = question.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        chat.append(ChatMessage(role: .owner, text: trimmed))
        let history = chat.suffix(10).map { message in
            AgentHistoryMessage(
                role: message.role == .owner ? "owner" : "assistant",
                text: message.text
            )
        }
        isSending = true
        defer { isSending = false }
        do {
            let timeline = householdEvents.isEmpty ? events : householdEvents
            let reportContext = householdReport ?? report
            let answer = try await client.ask(
                question: trimmed,
                timeline: timeline,
                report: reportContext,
                history: Array(history)
            )
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
                insertVisibleEvent(event)
                await refreshReports()
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

    var latestHouseholdEvent: TimelineEvent? { householdEvents.first }

    var overallLevel: String { report?.overall ?? "normal" }

    var householdOverallLevel: String { householdReport?.overall ?? overallLevel }

    var selectedCat: CatProfile? {
        cats.first { $0.id == selectedCatId } ?? cats.first
    }

    private func ensureSelectedCat() {
        guard !cats.isEmpty else {
            selectedCatId = nil
            return
        }
        if let selectedCatId, cats.contains(where: { $0.id == selectedCatId }) {
            return
        }
        selectedCatId = cats[0].id
    }

    private func insertVisibleEvent(_ event: TimelineEvent) {
        householdEvents.insert(event, at: 0)
        if event.catId == nil || event.catId == selectedCatId {
            events.insert(event, at: 0)
        }
    }

    private func refreshReports() async {
        async let selectedReport = try? client.report(range: reportRange, catId: selectedCatId)
        async let householdReport = try? client.report(range: reportRange)
        let loadedSelectedReport = await selectedReport
        let loadedHouseholdReport = await householdReport
        if loadedSelectedReport == nil || loadedHouseholdReport == nil {
            applyMockReports(range: reportRange)
        }
        if let loadedSelectedReport {
            self.report = loadedSelectedReport
        }
        if let loadedHouseholdReport {
            self.householdReport = loadedHouseholdReport
        }
    }

    private func applyMockData(catId: String?, range: ReportRange) {
        guard let mockData else { return }
        cats = mockData.cats
        ensureSelectedCat()
        let sortedEvents = mockData.events.sorted {
            (Format.date($0.time) ?? .distantPast) > (Format.date($1.time) ?? .distantPast)
        }
        householdEvents = sortedEvents
        events = eventsForSelectedCat(from: sortedEvents, catId: catId ?? selectedCatId)
        applyMockReports(range: range)
    }

    private func applyMockReports(range: ReportRange) {
        let timeline = householdEvents.isEmpty ? mockData?.events ?? [] : householdEvents
        let selectedTimeline = events.isEmpty ? eventsForSelectedCat(from: timeline, catId: selectedCatId) : events
        householdReport = MockDataStore.report(for: timeline, range: range)
        report = MockDataStore.report(for: selectedTimeline, range: range)
    }

    private func eventsForSelectedCat(from events: [TimelineEvent], catId: String?) -> [TimelineEvent] {
        guard let catId, !catId.isEmpty else { return events }
        return events.filter { $0.catId == catId }
    }
}
