import Foundation

// MARK: - API models (mirror the FastAPI backend JSON)

struct CatProfile: Codable, Identifiable, Hashable {
    let id: String
    var ownerId: String?
    var ownerUsername: String?
    let name: String
    let initials: String
    let age: String
    let birthDate: String
    var device: String?
    let accent: String
}

struct TimelineEvent: Codable, Identifiable, Hashable {
    let id: String
    let catId: String?
    let catName: String?
    let time: String
    let source: String
    let state: String
    let intent: String
    let behaviorLabel: String
    let soundType: String
    let confidence: Double
    let riskLevel: String
    let signals: [String]
    let summary: String
    let suggestion: String
}

struct Alert: Codable, Identifiable, Hashable {
    var id: String { signal }
    let signal: String
    let level: String
    let title: String
    let evidence: [String]
    let suggestion: String
    let confidence: Double
}

struct EventCounts: Codable, Hashable {
    var eating = 0
    var litter = 0
    var active = 0
    var resting = 0
    var grooming = 0
    var vocal = 0
    var review = 0
}

struct HealthReport: Codable, Hashable {
    let dateLabel: String
    let range: String
    let totalEvents: Int
    let counts: EventCounts
    let alerts: [Alert]
    let overall: String
    let summary: String
}

struct AuthUser: Codable, Identifiable, Hashable {
    let id: String
    let username: String
    let displayName: String
    var createdAt: String?
}

struct ScenarioType: Codable, Identifiable, Hashable {
    let id: String
    let label: String
}

struct LiveKitToken: Codable, Sendable {
    let configured: Bool
    let url: String
    let room: String
    let identity: String
    let token: String
}

// MARK: - Local UI models

enum ReportRange: String, CaseIterable, Identifiable {
    case day, week, month
    var id: String { rawValue }
    var label: String {
        switch self {
        case .day: return "Day"
        case .week: return "Week"
        case .month: return "Month"
        }
    }
}

struct ChatMessage: Identifiable, Hashable {
    enum Role { case owner, assistant }
    let id = UUID()
    let role: Role
    let text: String
    var provider: String?
}

struct AgentHistoryMessage: Codable, Hashable {
    let role: String
    let text: String
}

// MARK: - Response envelopes

struct HealthResponse: Codable {
    let ok: Bool
    let service: String?
    let mongodb: String?
}
struct AuthResponse: Codable { let ok: Bool; let user: AuthUser; let token: String }
struct MeResponse: Codable { let ok: Bool; let user: AuthUser }
struct CatsResponse: Codable { let ok: Bool; let cats: [CatProfile]; let owner: String? }
struct CatResponse: Codable { let ok: Bool; let cat: CatProfile }
struct EventsResponse: Codable { let ok: Bool; let events: [TimelineEvent]; let source: String? }
struct ReportResponse: Codable { let ok: Bool; let report: HealthReport }
struct AgentResponse: Codable { let ok: Bool; let answer: String; let provider: String }
struct ScenariosResponse: Codable { let ok: Bool; let scenarios: [ScenarioType] }
struct ClipFileInfo: Codable { let name: String; let type: String; let size: Int? }
struct ClipAnalysisResponse: Codable {
    let ok: Bool
    let provider: String
    let text: String
    let rawText: String?
    let file: ClipFileInfo?
    let event: TimelineEvent?
    let analysis: TimelineEvent?
}
