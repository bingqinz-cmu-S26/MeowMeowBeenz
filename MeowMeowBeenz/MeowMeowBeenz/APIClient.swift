import Foundation

/// Thin async wrapper over the MeowMeowBeenz FastAPI backend.
/// Sendable value type so it can be used freely across actors.
struct APIClient: Sendable {
    var baseURL: URL
    var token: String?

    struct APIError: LocalizedError {
        let message: String
        var errorDescription: String? { message }
    }

    // MARK: Core request

    private func request<T: Decodable>(
        _ path: String,
        method: String = "GET",
        body: Data? = nil,
        headers: [String: String]? = nil,
        authorized: Bool = false,
        as type: T.Type = T.self
    ) async throws -> T {
        guard let url = URL(string: path, relativeTo: baseURL) else {
            throw APIError(message: "Bad URL: \(path)")
        }
        var req = URLRequest(url: url)
        req.httpMethod = method
        req.timeoutInterval = 20
        if let body {
            req.httpBody = body
            if let headers, let contentType = headers["Content-Type"] {
                req.setValue(contentType, forHTTPHeaderField: "Content-Type")
            } else {
                req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            }
            headers?.forEach { key, value in
                req.setValue(value, forHTTPHeaderField: key)
            }
        }
        if authorized, let token {
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        let (data, response) = try await URLSession.shared.data(for: req)
        guard let http = response as? HTTPURLResponse else {
            throw APIError(message: "No HTTP response")
        }
        guard (200..<300).contains(http.statusCode) else {
            throw APIError(message: Self.errorDetail(data) ?? "Request failed (\(http.statusCode))")
        }
        do {
            return try JSONDecoder().decode(T.self, from: data)
        } catch {
            throw APIError(message: "Could not decode \(T.self): \(error.localizedDescription)")
        }
    }

    private static func errorDetail(_ data: Data) -> String? {
        guard let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return nil }
        return parseError(from: obj)
    }

    private static func parseError(from value: Any) -> String? {
        switch value {
        case let dict as [String: Any]:
            if let detail = dict["detail"] {
                if let parsed = parseError(from: detail) {
                    return parsed
                }
            }
            if let error = dict["error"] {
                if let parsed = parseError(from: error) {
                    return parsed
                }
            }
            if let message = dict["message"] as? String, !message.isEmpty {
                return message
            }
            if let msg = dict["detail"] as? String {
                return msg
            }
            return nil
        case let array as [Any]:
            for item in array {
                if let parsed = parseError(from: item) {
                    return parsed
                }
            }
            return nil
        case let text as String:
            return text
        default:
            return nil
        }
    }

    private static func encode<T: Encodable>(_ value: T) -> Data? {
        try? JSONEncoder().encode(value)
    }

    // MARK: Endpoints

    func health() async throws -> HealthResponse {
        try await request("/api/health", as: HealthResponse.self)
    }

    func login(username: String, password: String) async throws -> AuthResponse {
        let body = ["username": username, "password": password]
        return try await request("/api/auth/login", method: "POST", body: Self.encode(body))
    }

    func register(username: String, password: String, displayName: String?) async throws -> AuthResponse {
        let body = ["username": username, "password": password, "display_name": displayName ?? username]
        return try await request("/api/auth/register", method: "POST", body: Self.encode(body))
    }

    func me() async throws -> AuthUser {
        try await request("/api/auth/me", authorized: true, as: MeResponse.self).user
    }

    func cats() async throws -> [CatProfile] {
        try await request("/api/cats", authorized: true, as: CatsResponse.self).cats
    }

    func createCat(name: String, birthDate: String, device: String?) async throws -> CatProfile {
        let body = ["name": name, "birth_date": birthDate, "device": device ?? ""]
        return try await request("/api/cats", method: "POST", body: Self.encode(body), authorized: true, as: CatResponse.self).cat
    }

    func events() async throws -> [TimelineEvent] {
        try await request("/api/events", as: EventsResponse.self).events
    }

    func seedEvents() async throws -> [TimelineEvent] {
        try await request("/api/events/seed", method: "POST", as: EventsResponse.self).events
    }

    func addScenario(_ type: String) async throws -> TimelineEvent {
        struct EventResponse: Codable { let ok: Bool; let event: TimelineEvent }
        return try await request("/api/events/scenario/\(type)", method: "POST", as: EventResponse.self).event
    }

    func scenarios() async throws -> [ScenarioType] {
        try await request("/api/events/scenarios", as: ScenariosResponse.self).scenarios
    }

    func report(range: ReportRange) async throws -> HealthReport {
        try await request("/api/report?range=\(range.rawValue)", as: ReportResponse.self).report
    }

    func ask(question: String, timeline: [TimelineEvent], report: HealthReport?) async throws -> AgentResponse {
        struct AgentBody: Encodable { let question: String; let timeline: [TimelineEvent]; let report: HealthReport? }
        let body = AgentBody(question: question, timeline: timeline, report: report)
        return try await request("/api/agent", method: "POST", body: Self.encode(body))
    }

    func livekitToken(room: String? = nil, identity: String? = nil) async throws -> LiveKitToken {
        struct Body: Encodable { let room: String?; let identity: String? }
        struct Resp: Codable {
            let ok: Bool
            let configured: Bool?
            let url: String?
            let room: String?
            let identity: String?
            let token: String?
        }
        let r: Resp = try await request("/api/livekit-token", method: "POST",
                                        body: Self.encode(Body(room: room, identity: identity)))
        return LiveKitToken(configured: r.configured ?? true, url: r.url ?? "",
                            room: r.room ?? "", identity: r.identity ?? "", token: r.token ?? "")
    }

    func analyzeClip(fileData: Data, filename: String, mimeType: String) async throws -> ClipAnalysisResponse {
        let boundary = "Boundary-\(UUID().uuidString)"
        let body = Self.multipartBody(
            fileFieldName: "clip",
            fileName: filename,
            mimeType: mimeType,
            fileData: fileData,
            boundary: boundary
        )
        let contentType = "multipart/form-data; boundary=\(boundary)"
        return try await request("/api/analyze-clip",
                                 method: "POST",
                                 body: body,
                                 headers: ["Content-Type": contentType],
                                 as: ClipAnalysisResponse.self)
    }

    private static func multipartBody(fileFieldName: String,
                                     fileName: String,
                                     mimeType: String,
                                     fileData: Data,
                                     boundary: String) -> Data {
        let lineBreak = "\r\n"
        var body = Data()
        let append = { (string: String) in
            body.append(string.data(using: .utf8)!)
        }

        append("--\(boundary)\(lineBreak)")
        append("Content-Disposition: form-data; name=\"\(fileFieldName)\"; filename=\"\(fileName)\"\(lineBreak)")
        append("Content-Type: \(mimeType)\(lineBreak)\(lineBreak)")
        body.append(fileData)
        append(lineBreak)
        append("--\(boundary)--\(lineBreak)")
        return body
    }
}
