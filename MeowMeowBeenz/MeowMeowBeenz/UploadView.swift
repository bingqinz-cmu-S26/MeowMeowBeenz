import SwiftUI
import UniformTypeIdentifiers
import UIKit
import PhotosUI
import AVFoundation
import AVKit

struct UploadView: View {
    @Environment(AppModel.self) private var app

    @State private var showCamera = false
    @State private var selectedPhotoItem: PhotosPickerItem?
    @State private var isAnalyzing = false
    @State private var statusMessage: String? = "Pick a video to analyze."
    @State private var lastProvider: String?
    @State private var lastSummary: String?
    @State private var lastRawResponse: String?
    @State private var lastEvent: TimelineEvent?
    @State private var lastFile: ClipFileInfo?
    @State private var lastError: String?
    @State private var playbackItem: VideoPlaybackItem?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    UploadSourcePanel(
                        canRecordVideo: CameraVideoPicker.canRecordVideo,
                        isAnalyzing: isAnalyzing,
                        capture: captureWithCamera,
                        selectedPhotoItem: $selectedPhotoItem
                    )

                    if isAnalyzing || lastError != nil || statusMessage != nil {
                        UploadStatusCard(
                            isAnalyzing: isAnalyzing,
                            message: statusMessage,
                            error: lastError
                        )
                    }

                    if let event = lastEvent {
                        SoftCard(
                            title: "Latest analysis",
                            subtitle: "Saved to gallery",
                            icon: "sparkles.tv",
                            accent: Risk(event.riskLevel).color
                        ) {
                            ClipResultView(
                                event: event,
                                provider: lastProvider,
                                file: lastFile
                            )
                        }
                    } else if let summary = lastSummary {
                        SoftCard(
                            title: "Latest analysis",
                            subtitle: lastProvider.map { "\($0.capitalized) result" },
                            icon: "sparkles",
                            accent: .purple
                        ) {
                            Text(cleanModelText(summary))
                                .font(.footnote)
                                .foregroundStyle(.secondary)
                        }
                    }

                    UploadGallerySection(
                        items: app.uploadGallery,
                        videoURL: { item in app.videoURL(for: item) },
                        play: { item in
                            if let url = app.videoURL(for: item) {
                                playbackItem = VideoPlaybackItem(url: url)
                            } else {
                                lastError = "This video is not available for playback."
                            }
                        },
                        delete: { item in
                            Task { await app.deleteUpload(item) }
                        }
                    )
                }
                .padding(16)
            }
            .background(AppBackdrop())
            .navigationTitle("Upload")
            .task {
                await app.refreshUploadGallery()
            }
            .sheet(isPresented: $showCamera) {
                CameraVideoPicker { result in
                    showCamera = false
                    Task { await handlePickedVideo(result: result) }
                }
            }
            .sheet(item: $playbackItem) { item in
                VideoPlayerSheet(url: item.url)
            }
            .onChange(of: selectedPhotoItem) { _, item in
                Task { await analyzePhotoItem(item) }
            }
        }
    }

    private func captureWithCamera() {
        guard CameraVideoPicker.canRecordVideo else {
            statusMessage = "Camera is not available here. Pick a video from Photos instead."
            return
        }
        showCamera = true
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

private struct UploadSourcePanel: View {
    let canRecordVideo: Bool
    let isAnalyzing: Bool
    let capture: () -> Void
    @Binding var selectedPhotoItem: PhotosPickerItem?

    var body: some View {
        SoftCard(
            title: "Source",
            subtitle: "Create a new memory for the analysis gallery",
            icon: "plus.viewfinder",
            accent: .blue
        ) {
            VStack(spacing: 10) {
                Button(action: capture) {
                    UploadSourceRow(
                        title: "Take a video",
                        subtitle: canRecordVideo ? "Capture a live cat moment" : "Camera unavailable here",
                        systemImage: "video.badge.plus",
                        accent: .blue
                    )
                }
                .buttonStyle(.plain)
                .disabled(!canRecordVideo || isAnalyzing)

                Divider()

                PhotosPicker(selection: $selectedPhotoItem, matching: .videos) {
                    UploadSourceRow(
                        title: "Pick from Photos",
                        subtitle: "Analyze an existing clip",
                        systemImage: "photo.on.rectangle",
                        accent: .cyan
                    )
                }
                .buttonStyle(.plain)
                .disabled(isAnalyzing)
            }
        }
    }
}

private struct UploadSourceRow: View {
    let title: String
    let subtitle: String
    let systemImage: String
    let accent: Color

    var body: some View {
        HStack(spacing: 14) {
            Image(systemName: systemImage)
                .font(.title2.weight(.semibold))
                .foregroundStyle(accent)
                .frame(width: 34)
            VStack(alignment: .leading, spacing: 3) {
                Text(title)
                    .font(.body.weight(.semibold))
                    .foregroundStyle(.primary)
                Text(subtitle)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Image(systemName: "chevron.right")
                .font(.caption.weight(.bold))
                .foregroundStyle(.tertiary)
        }
        .contentShape(Rectangle())
        .padding(.vertical, 4)
    }
}

private struct UploadStatusCard: View {
    let isAnalyzing: Bool
    let message: String?
    let error: String?

    var body: some View {
        SoftCard(accent: error == nil ? .blue : .red) {
            HStack(alignment: .top, spacing: 12) {
                if isAnalyzing {
                    ProgressView()
                        .controlSize(.small)
                } else {
                    Image(systemName: error == nil ? "checkmark.circle" : "exclamationmark.triangle")
                        .foregroundStyle(error == nil ? .green : .red)
                }
                VStack(alignment: .leading, spacing: 4) {
                    Text(error ?? message ?? "Ready to analyze.")
                        .font(.footnote.weight(.medium))
                        .foregroundStyle(error == nil ? Color.secondary : Color.red)
                    if isAnalyzing {
                        Text("The result will be saved as a gallery card.")
                            .font(.caption)
                            .foregroundStyle(.tertiary)
                    }
                }
            }
        }
    }
}

private struct UploadGallerySection: View {
    let items: [UploadGalleryItem]
    let videoURL: (UploadGalleryItem) -> URL?
    let play: (UploadGalleryItem) -> Void
    let delete: (UploadGalleryItem) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: 3) {
                    Text("Analysis Gallery")
                        .font(.title3.weight(.bold))
                    Text("\(items.count) saved \(items.count == 1 ? "moment" : "moments")")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                if !items.isEmpty {
                    Image(systemName: "square.grid.2x2")
                        .foregroundStyle(.secondary)
                }
            }

            if items.isEmpty {
                EmptyUploadGalleryView()
            } else {
                LazyVStack(spacing: 14) {
                    ForEach(items) { item in
                        UploadGalleryCard(
                            item: item,
                            videoURL: videoURL(item),
                            play: { play(item) },
                            delete: { delete(item) }
                        )
                    }
                }
            }
        }
    }
}

private struct EmptyUploadGalleryView: View {
    var body: some View {
        SoftCard(accent: .purple) {
            VStack(alignment: .leading, spacing: 10) {
                Image(systemName: "photo.stack")
                    .font(.largeTitle)
                    .foregroundStyle(.purple)
                Text("Your uploaded cat moments will live here.")
                    .font(.headline.weight(.semibold))
                Text("Each new video creates a saved card with the mood insight, risk level, confidence, and source file details.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }
}

private struct UploadGalleryCard: View {
    let item: UploadGalleryItem
    let videoURL: URL?
    let play: () -> Void
    let delete: () -> Void

    private var event: TimelineEvent? { item.event }
    private var risk: Risk { Risk(event?.riskLevel ?? "normal") }

    var body: some View {
        SoftCard(accent: risk.color) {
            VStack(alignment: .leading, spacing: 14) {
                HStack(alignment: .top, spacing: 12) {
                    UploadPoster(
                        event: event,
                        filename: item.filename,
                        risk: risk,
                        videoURL: videoURL,
                        play: play
                    )
                    VStack(alignment: .leading, spacing: 8) {
                        HStack(alignment: .top) {
                            VStack(alignment: .leading, spacing: 3) {
                                Text(event?.state ?? "Cat mood insight")
                                    .font(.headline.weight(.semibold))
                                    .lineLimit(2)
                                Text(Format.relative(item.createdAt))
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                            Spacer(minLength: 8)
                            RiskBadge(level: event?.riskLevel ?? "normal")
                        }

                        Text(cleanSummary(item.summary, event: event))
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                            .lineLimit(4)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }

                if let event {
                    HStack(spacing: 8) {
                        GalleryMetric(
                            title: "Mood",
                            value: prettify(event.intent),
                            icon: "heart.text.square"
                        )
                        GalleryMetric(
                            title: "Sound",
                            value: prettify(event.soundType),
                            icon: "waveform"
                        )
                        GalleryMetric(
                            title: "Confidence",
                            value: Format.percent(event.confidence),
                            icon: "gauge.with.dots.needle.bottom.50percent"
                        )
                    }
                }

                HStack(spacing: 10) {
                    Label(item.provider.capitalized, systemImage: "sparkles")
                    Text(fileLabel(item.file, fallback: item.mimeType))
                    Spacer()
                    Button(action: play) {
                        Image(systemName: "play.circle.fill")
                    }
                    .buttonStyle(.borderless)
                    .disabled(videoURL == nil)
                    Button(role: .destructive, action: delete) {
                        Image(systemName: "trash")
                    }
                    .buttonStyle(.borderless)
                }
                .font(.caption)
                .foregroundStyle(.tertiary)

                if let raw = item.rawResponse, !raw.isEmpty {
                    DisclosureGroup("Raw response") {
                        Text(raw)
                            .font(.caption.monospaced())
                            .foregroundStyle(.secondary)
                            .textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.top, 6)
                    }
                    .font(.caption)
                }
            }
        }
    }

    private func cleanSummary(_ summary: String, event: TimelineEvent?) -> String {
        let text = event?.summary ?? summary
        return text
            .replacingOccurrences(of: "```json", with: "")
            .replacingOccurrences(of: "```", with: "")
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private func prettify(_ value: String) -> String {
        value
            .replacingOccurrences(of: ".", with: " ")
            .replacingOccurrences(of: "_", with: " ")
            .split(separator: " ")
            .map { word in word.prefix(1).uppercased() + word.dropFirst() }
            .joined(separator: " ")
    }

    private func fileLabel(_ file: ClipFileInfo?, fallback: String) -> String {
        guard let file, let size = file.size else { return fallback }
        let mb = Double(size) / 1_048_576
        if mb >= 0.1 {
            return String(format: "%.1f MB", mb)
        }
        return "\(size) bytes"
    }
}

private struct UploadPoster: View {
    let event: TimelineEvent?
    let filename: String
    let risk: Risk
    let videoURL: URL?
    let play: () -> Void

    @State private var thumbnail: UIImage?

    var body: some View {
        Button(action: play) {
            ZStack(alignment: .bottomLeading) {
                Group {
                    if let thumbnail {
                        Image(uiImage: thumbnail)
                            .resizable()
                            .scaledToFill()
                    } else {
                        RoundedRectangle(cornerRadius: 16, style: .continuous)
                            .fill(
                                LinearGradient(
                                    colors: [risk.color.opacity(0.26), Color.blue.opacity(0.14), Color.white.opacity(0.22)],
                                    startPoint: .topLeading,
                                    endPoint: .bottomTrailing
                                )
                            )
                        Image(systemName: iconName)
                            .font(.system(size: 34, weight: .semibold))
                            .foregroundStyle(risk.color)
                    }
                }
                .frame(width: 96, height: 118)
                .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))

                LinearGradient(
                    colors: [.clear, .black.opacity(0.5)],
                    startPoint: .center,
                    endPoint: .bottom
                )
                .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))

                Image(systemName: "play.fill")
                    .font(.caption.weight(.bold))
                    .foregroundStyle(.white)
                    .padding(9)
                    .background(risk.color.opacity(0.86), in: Circle())
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .center)

                VStack(alignment: .leading, spacing: 2) {
                    Text("Video")
                        .font(.caption2.weight(.bold))
                        .foregroundStyle(.white.opacity(0.9))
                    Text(filename)
                        .font(.caption2)
                        .lineLimit(1)
                        .foregroundStyle(.white.opacity(0.86))
                }
                .padding(8)
            }
            .frame(width: 96, height: 118)
            .overlay(
                RoundedRectangle(cornerRadius: 16, style: .continuous)
                    .stroke(Color.white.opacity(0.55), lineWidth: 0.8)
            )
        }
        .buttonStyle(.plain)
        .disabled(videoURL == nil)
        .task(id: videoURL?.absoluteString ?? filename) {
            await loadThumbnail()
        }
    }

    @MainActor
    private func loadThumbnail() async {
        guard thumbnail == nil, let videoURL else { return }
        let asset = AVURLAsset(url: videoURL)
        let generator = AVAssetImageGenerator(asset: asset)
        generator.appliesPreferredTrackTransform = true
        generator.maximumSize = CGSize(width: 360, height: 360)
        let preferredTime = CMTime(seconds: 0.45, preferredTimescale: 600)
        if let image = try? generator.copyCGImage(at: preferredTime, actualTime: nil) {
            thumbnail = UIImage(cgImage: image)
            return
        }
        if let image = try? generator.copyCGImage(at: .zero, actualTime: nil) {
            thumbnail = UIImage(cgImage: image)
        }
    }

    private var iconName: String {
        guard let event else { return "play.rectangle.fill" }
        if event.behaviorLabel.contains("eating") { return "fork.knife.circle.fill" }
        if event.behaviorLabel.contains("play") { return "sparkles.rectangle.stack.fill" }
        if event.soundType.contains("yowl") || event.soundType.contains("meow") { return "waveform.circle.fill" }
        if event.behaviorLabel.contains("rest") || event.behaviorLabel.contains("lying") { return "moon.circle.fill" }
        return "play.rectangle.fill"
    }
}

private struct VideoPlaybackItem: Identifiable {
    let id = UUID()
    let url: URL
}

private struct VideoPlayerSheet: View {
    let url: URL
    @State private var player: AVPlayer

    init(url: URL) {
        self.url = url
        _player = State(initialValue: AVPlayer(url: url))
    }

    var body: some View {
        NavigationStack {
            VideoPlayer(player: player)
                .ignoresSafeArea(edges: .bottom)
                .navigationTitle("Cat Moment")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .topBarTrailing) {
                        ShareLink(item: url) {
                            Image(systemName: "square.and.arrow.up")
                        }
                    }
                }
                .onAppear {
                    player.play()
                }
                .onDisappear {
                    player.pause()
                }
        }
    }
}

private struct GalleryMetric: View {
    let title: String
    let value: String
    let icon: String

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            Image(systemName: icon)
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(value)
                .font(.caption.weight(.semibold))
                .lineLimit(2)
                .minimumScaleFactor(0.75)
            Text(title)
                .font(.caption2)
                .foregroundStyle(.tertiary)
        }
        .frame(maxWidth: .infinity, minHeight: 74, alignment: .leading)
        .padding(10)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
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
