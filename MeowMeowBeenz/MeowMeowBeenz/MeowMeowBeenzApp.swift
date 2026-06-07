import SwiftUI

@main
struct MeowMeowBeenzApp: App {
    @State private var app = AppModel()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(app)
                .task { await app.bootstrap() }
        }
    }
}
