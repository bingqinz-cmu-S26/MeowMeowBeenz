import SwiftUI
import UniformTypeIdentifiers
import UIKit

struct UploadView: View {
    @Environment(AppModel.self) private var app

    @State private var showCamera = false
    @State private var showFileImporter = false
    @State private var isAnalyzing = false
    @State private var statusMessage: String? = "Pick a video to analyze."
    @State private var lastProvider: String?
    @State private var lastSummary: String?
    @State private var lastError: String?

    var body: some View {
        NavigationStack {
            Form {
                Section("Source") {
                    Button(action: captureWithCamera) {
                        Label("Take a video", systemImage: "video.badge.plus")
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

                if let summary = lastSummary {
                    Section("Latest result") {
                        Text(summary).font(.footnote).foregroundStyle(.secondary)
                        if let provider = lastProvider {
                            Text("Provider: \(provider)")
                                .font(.footnote)
                                .foregroundStyle(.tertiary)
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
        }
    }

    private func captureWithCamera() {
        guard UIImagePickerController.isSourceTypeAvailable(.camera) else {
            statusMessage = "Camera is not available on this device."
            return
        }
        showCamera = true
    }

    private func openFileImporter() {
        showFileImporter = true
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
                return
            }
            lastError = app.errorMessage ?? "Analysis failed."
            statusMessage = "Analysis failed."
        } catch {
            lastError = "Could not read selected video: \(error.localizedDescription)"
            statusMessage = "Could not analyze selected video."
        }
    }
}

private extension String {
    func ifEmpty(_ fallback: String) -> String {
        isEmpty ? fallback : self
    }
}

private struct CameraVideoPicker: UIViewControllerRepresentable {
    let onFinish: (Result<URL, Error>) -> Void

    func makeUIViewController(context: Context) -> UIImagePickerController {
        let picker = UIImagePickerController()
        picker.sourceType = .camera
        picker.mediaTypes = [UTType.movie.identifier]
        picker.videoQuality = .typeHigh
        picker.delegate = context.coordinator
        return picker
    }

    func updateUIViewController(_ uiViewController: UIImagePickerController, context: Context) {}

    func makeCoordinator() -> Coordinator {
        Coordinator(onFinish: onFinish)
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
