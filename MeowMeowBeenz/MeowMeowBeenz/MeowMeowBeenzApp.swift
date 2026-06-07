import SwiftUI
import LiveKit

@main
struct MeowMeowBeenzApp: App {
    @State private var app = AppModel()

    init() {
        AudioManager.prepare()
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(app)
                .task {
                    try? await AudioManager.shared.setRecordingAlwaysPreparedMode(true)
                    await app.bootstrap()
                }
        }
    }
}
