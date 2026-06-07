import SwiftUI
import UniformTypeIdentifiers
import UIKit
import PhotosUI

struct UploadView: View {
    @Environment(AppModel.self) private var app

    @State private var showCamera = false
    @State private var showFileImporter = false
    @State private var selectedPhotoItem: PhotosPickerItem?
    @State private var isAnalyzing = false
    @State private var statusMessage: String? = "Pick a video to analyze."
    @State private var lastProvider: String?
    @State private var lastSummary: String?
    @State private var lastRawResponse: String?
    @State private var lastEvent: TimelineEvent?
    @State private var lastFile: ClipFileInfo?
    @State private var lastError: String?

    var body: some View {
        NavigationStack {
            Form {
                Section("Source") {
                    Button(action: captureWithCamera) {
                        Label("Take a video", systemImage: "video.badge.plus")
                    }
                    PhotosPicker(selection: $selectedPhotoItem, matching: .videos) {
                        Label("Pick from Photos", systemImage: "photo.on.rectangle")
                    }
                    Button(action: openFileImporter) {
                        Label("Upload a video", systemImage: "video")
                    }
                }

                if isAnalyzing {
                    HStack {
                        ProgressView()
                        Text("Analyzing video…")
                            .foregroundStyle(.secondary)
                    }
                }

                if let event = lastEvent {
                    Section("Latest result") {
                        ClipResultView(
                            event: event,
                            provider: lastProvider,
                            file: lastFile
                        )
                    }
                } else if let summary = lastSummary {
                    Section("Latest result") {
                        Text(cleanModelText(summary)).font(.footnote).foregroundStyle(.secondary)
                        if let provider = lastProvider {
                            Text("Provider: \(provider)")
                                .font(.footnote)
                                .foregroundStyle(.tertiary)
                        }
                    }
                }

                if let rawResponse = lastRawResponse, !rawResponse.isEmpty {
                    Section(lastProvider == "gemini" ? "Gemini raw response" : "Model raw response") {
                        DisclosureGroup("Show raw response") {
                            ScrollView(.vertical) {
                                Text(rawResponse)
                                    .font(.caption.monospaced())
                                    .foregroundStyle(.secondary)
                                    .textSelection(.enabled)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .fixedSize(horizontal: false, vertical: true)
                                    .padding(.vertical, 6)
                            }
                            .frame(minHeight: 160, maxHeight: 360)
                        }
                    }
                }

                if let error = lastError {
                    Text(error)
                        .foregroundStyle(.red)
                        .font(.footnote)
                }

                if let message = statusMessage {
                    HStack(alignment: .top) {
                        Text(message)
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .listStyle(.insetGrouped)
            .navigationTitle("Upload")
            .sheet(isPresented: $showCamera) {
                CameraVideoPicker { result in
                    showCamera = false
                    Task { await handlePickedVideo(result: result) }
                }
            }
            .fileImporter(
                isPresented: $showFileImporter,
                allowedContentTypes: [.movie, .video],
                allowsMultipleSelection: false
            ) { result in
                switch result {
                case .success(let urls):
                    guard let url = urls.first else {
                        lastError = "No video was selected."
                        statusMessage = "Please choose a video file first."
                        return
                    }
                    Task { await analyzeVideo(at: url) }
                case .failure(let error):
                    lastError = "Could not select video: \(error.localizedDescription)"
                }
            }
            .onChange(of: selectedPhotoItem) { _, item in
                Task { await analyzePhotoItem(item) }
            }
        }
    }

    private func captureWithCamera() {
        guard CameraVideoPicker.canRecordVideo else {
            statusMessage = "Camera video is not available here. Use Upload a video instead."
            showFileImporter = true
            return
        }
        showCamera = true
    }

    private func openFileImporter() {
        showFileImporter = true
    }

    @MainActor
    private func analyzePhotoItem(_ item: PhotosPickerItem?) async {
        guard let item else { return }

        isAnalyzing = true
        lastSummary = nil
        lastRawResponse = nil
        lastEvent = nil
        lastFile = nil
        lastProvider = nil
        lastError = nil
        statusMessage = "Loading video from Photos..."
        defer {
            isAnalyzing = false
            selectedPhotoItem = nil
        }

        do {
            guard let data = try await item.loadTransferable(type: Data.self) else {
                lastError = "Could not read the selected video from Photos."
                statusMessage = "Could not analyze selected video."
                return
            }
            let contentType = item.supportedContentTypes.first { type in
                type.conforms(to: .movie) || type.conforms(to: .video)
            } ?? UTType(filenameExtension: "mp4") ?? .movie
            let fileExtension = contentType.preferredFilenameExtension ?? "mp4"
            let filename = "photos-upload-\(UUID().uuidString).\(fileExtension)"
            let mimeType = contentType.preferredMIMEType ?? "video/mp4"

            statusMessage = "Uploading and analyzing..."
            let response = await app.analyzeUploadedVideo(fileData: data, filename: filename, mimeType: mimeType)
            if let response {
                statusMessage = "Analysis complete."
                lastProvider = response.provider
                lastSummary = response.text
                lastRawResponse = response.rawText ?? response.text
                lastEvent = response.event ?? response.analysis
                lastFile = response.file
                return
            }
            lastError = app.errorMessage ?? "Analysis failed."
            statusMessage = "Analysis failed."
        } catch {
            lastError = "Could not read selected video: \(error.localizedDescription)"
            statusMessage = "Could not analyze selected video."
        }
    }

    @MainActor
    private func handlePickedVideo(result: Result<URL, Error>) async {
        switch result {
        case .success(let url):
            await analyzeVideo(at: url)
        case .failure(let error):
            if error is VideoCaptureError {
                statusMessage = "Camera capture cancelled."
                lastError = nil
            } else {
                statusMessage = "Video capture did not finish."
                lastError = error.localizedDescription
            }
        }
    }

    @MainActor
    private func analyzeVideo(at url: URL) async {
        let hasSecurityScope = url.startAccessingSecurityScopedResource()
        defer {
            if hasSecurityScope { url.stopAccessingSecurityScopedResource() }
            isAnalyzing = false
        }

        isAnalyzing = true
        lastSummary = nil
        lastRawResponse = nil
        lastEvent = nil
        lastFile = nil
        lastProvider = nil
        lastError = nil
        statusMessage = "Uploading and analyzing..."

        do {
            let data = try Data(contentsOf: url)
            let filename = url.lastPathComponent.ifEmpty("uploaded-clip.mov")
            let mimeType = app.mimeType(for: url)
            let response = await app.analyzeUploadedVideo(fileData: data, filename: filename, mimeType: mimeType)

            if let response {
                statusMessage = "Analysis complete."
                lastProvider = response.provider
                lastSummary = response.text
                lastRawResponse = response.rawText ?? response.text
                lastEvent = response.event ?? response.analysis
                lastFile = response.file
                return
            }
            lastError = app.errorMessage ?? "Analysis failed."
            statusMessage = "Analysis failed."
        } catch {
            lastError = "Could not read selected video: \(error.localizedDescription)"
            statusMessage = "Could not analyze selected video."
        }
    }

    private func cleanModelText(_ text: String) -> String {
        text
            .replacingOccurrences(of: "```json", with: "")
            .replacingOccurrences(of: "```", with: "")
            .replacingOccurrences(of: "thought", with: "")
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }
}

private extension String {
    func ifEmpty(_ fallback: String) -> String {
        isEmpty ? fallback : self
    }
}

private struct ClipResultView: View {
    let event: TimelineEvent
    let provider: String?
    let file: ClipFileInfo?

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 8) {
                    Label(event.state, systemImage: iconName)
                        .font(.headline)
                        .lineLimit(2)
                    Spacer(minLength: 8)
                    Text(event.riskLevel.capitalized)
                        .font(.caption.weight(.semibold))
                        .padding(.horizontal, 10)
                        .padding(.vertical, 5)
                        .background(riskColor.opacity(0.16), in: Capsule())
                        .foregroundStyle(riskColor)
                }
                Text(event.summary)
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }

            VStack(spacing: 10) {
                ResultMetricRow(title: "Intent", value: prettify(event.intent), systemImage: "target")
                ResultMetricRow(title: "Behavior", value: prettify(event.behaviorLabel), systemImage: "figure.walk")
                ResultMetricRow(title: "Sound", value: prettify(event.soundType), systemImage: "waveform")
                ResultMetricRow(title: "Confidence", value: "\(Int(event.confidence * 100))%", systemImage: "gauge.with.dots.needle.bottom.50percent")
            }

            ProgressView(value: event.confidence)
                .tint(riskColor)

            if !event.signals.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Signals")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.secondary)
                    FlowLayout(items: event.signals.map(prettify))
                }
            }

            if !event.suggestion.isEmpty {
                Label(event.suggestion, systemImage: "lightbulb")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }

            HStack {
                if let provider {
                    Label(provider.capitalized, systemImage: "sparkles")
                }
                Spacer()
                if let file {
                    Text(fileLabel(file))
                }
            }
            .font(.caption)
            .foregroundStyle(.tertiary)
        }
        .padding(.vertical, 6)
    }

    private var riskColor: Color {
        switch event.riskLevel.lowercased() {
        case "review": return .red
        case "watch": return .orange
        default: return .green
        }
    }

    private var iconName: String {
        if event.behaviorLabel.contains("eating") { return "fork.knife.circle" }
        if event.behaviorLabel.contains("play") { return "sparkle.magnifyingglass" }
        if event.soundType.contains("yowl") || event.soundType.contains("meow") { return "waveform.circle" }
        if event.behaviorLabel.contains("rest") || event.behaviorLabel.contains("lying") { return "moon.circle" }
        return "pawprint.circle"
    }

    private func prettify(_ value: String) -> String {
        value
            .replacingOccurrences(of: ".", with: " ")
            .replacingOccurrences(of: "_", with: " ")
            .split(separator: " ")
            .map { word in word.prefix(1).uppercased() + word.dropFirst() }
            .joined(separator: " ")
    }

    private func fileLabel(_ file: ClipFileInfo) -> String {
        guard let size = file.size else { return file.type }
        let mb = Double(size) / 1_048_576
        if mb >= 0.1 {
            return String(format: "%.1f MB", mb)
        }
        return "\(size) bytes"
    }
}

private struct ResultMetricRow: View {
    let title: String
    let value: String
    let systemImage: String

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: systemImage)
                .font(.caption)
                .foregroundStyle(.secondary)
                .frame(width: 18)
            Text(title)
                .font(.footnote)
                .foregroundStyle(.secondary)
            Spacer(minLength: 12)
            Text(value)
                .font(.footnote.weight(.medium))
                .multilineTextAlignment(.trailing)
                .foregroundStyle(.primary)
        }
    }
}

private struct FlowLayout: View {
    let items: [String]

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            ForEach(chunked(items), id: \.self) { row in
                HStack(spacing: 8) {
                    ForEach(row, id: \.self) { item in
                        Text(item)
                            .font(.caption.weight(.medium))
                            .padding(.horizontal, 10)
                            .padding(.vertical, 6)
                            .background(.thinMaterial, in: Capsule())
                    }
                }
            }
        }
    }

    private func chunked(_ values: [String]) -> [[String]] {
        var rows: [[String]] = []
        var current: [String] = []
        var currentLength = 0

        for value in values {
            let projected = currentLength + value.count
            if projected > 28, !current.isEmpty {
                rows.append(current)
                current = [value]
                currentLength = value.count
            } else {
                current.append(value)
                currentLength = projected + 2
            }
        }

        if !current.isEmpty {
            rows.append(current)
        }
        return rows
    }
}

private struct CameraVideoPicker: UIViewControllerRepresentable {
    let onFinish: (Result<URL, Error>) -> Void

    static var canRecordVideo: Bool {
        guard UIImagePickerController.isSourceTypeAvailable(.camera) else {
            return false
        }
        return !availableCameraMovieTypes().isEmpty
    }

    func makeUIViewController(context: Context) -> UIImagePickerController {
        let picker = UIImagePickerController()
        picker.sourceType = .camera
        let mediaTypes = Self.availableCameraMovieTypes()
        if !mediaTypes.isEmpty {
            picker.mediaTypes = mediaTypes
        }
        if Self.supportsVideoCaptureMode() {
            picker.cameraCaptureMode = .video
        }
        picker.videoQuality = .typeHigh
        picker.delegate = context.coordinator
        return picker
    }

    func updateUIViewController(_ uiViewController: UIImagePickerController, context: Context) {}

    func makeCoordinator() -> Coordinator {
        Coordinator(onFinish: onFinish)
    }

    private static func availableCameraMovieTypes() -> [String] {
        guard let mediaTypes = UIImagePickerController.availableMediaTypes(for: .camera) else {
            return []
        }
        return mediaTypes.filter { identifier in
            guard let type = UTType(identifier) else {
                return identifier == UTType.movie.identifier || identifier == UTType.video.identifier
            }
            return type.conforms(to: .movie) || type.conforms(to: .video)
        }
    }

    private static func supportsVideoCaptureMode() -> Bool {
        let devices: [UIImagePickerController.CameraDevice] = [.rear, .front]
        return devices.contains { device in
            guard UIImagePickerController.isCameraDeviceAvailable(device),
                  let modes = UIImagePickerController.availableCaptureModes(for: device) else {
                return false
            }
            return modes.contains(NSNumber(value: UIImagePickerController.CameraCaptureMode.video.rawValue))
        }
    }

    final class Coordinator: NSObject, UINavigationControllerDelegate, UIImagePickerControllerDelegate {
        let onFinish: (Result<URL, Error>) -> Void

        init(onFinish: @escaping (Result<URL, Error>) -> Void) {
            self.onFinish = onFinish
        }

        func imagePickerControllerDidCancel(_ picker: UIImagePickerController) {
            picker.dismiss(animated: true) {
                self.onFinish(.failure(VideoCaptureError.cancelled))
            }
        }

        func imagePickerController(_ picker: UIImagePickerController,
                                  didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey: Any]) {
            guard let sourceURL = info[.mediaURL] as? URL else {
                picker.dismiss(animated: true) {
                    self.onFinish(.failure(VideoCaptureError.missingMedia))
                }
                return
            }

            let destinationExtension = sourceURL.pathExtension.ifEmpty("mov")
            let destination = FileManager.default.temporaryDirectory.appendingPathComponent(
                "meowmeow-upload-\(UUID().uuidString).\(destinationExtension)"
            )

            let copiedURL: URL
            do {
                if FileManager.default.fileExists(atPath: destination.path) {
                    try FileManager.default.removeItem(at: destination)
                }
                try FileManager.default.copyItem(at: sourceURL, to: destination)
                copiedURL = destination
            } catch {
                picker.dismiss(animated: true) {
                    self.onFinish(.failure(error))
                }
                return
            }

            picker.dismiss(animated: true) {
                self.onFinish(.success(copiedURL))
            }
        }
    }
}

private enum VideoCaptureError: Error {
    case cancelled
    case missingMedia
}
