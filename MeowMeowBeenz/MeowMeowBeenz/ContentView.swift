import SwiftUI

struct ContentView: View {
    private enum Tab: Hashable {
        case home, data, reports, chat, upload
    }

    @State private var selectedTab: Tab = .home
    @State private var previousTab: Tab = .home
    @State private var isShowingUpload = false

    var body: some View {
        TabView(selection: $selectedTab) {
            HomeView()
                .tabItem { Label("Home", systemImage: "house") }
                .tag(Tab.home)

            DataView()
                .tabItem { Label("Data", systemImage: "chart.bar") }
                .tag(Tab.data)

            ReportsView()
                .tabItem { Label("Reports", systemImage: "doc.text") }
                .tag(Tab.reports)

            ChatView()
                .tabItem { Label("Chat", systemImage: "message") }
                .tag(Tab.chat)

            Color.clear
                .tabItem { Label("Upload", systemImage: "plus.circle.fill") }
                .tag(Tab.upload)
        }
        .onChange(of: selectedTab) { _, newTab in
            if newTab == .upload {
                isShowingUpload = true
                selectedTab = previousTab
            } else {
                previousTab = newTab
            }
        }
        .sheet(isPresented: $isShowingUpload) {
            UploadView()
        }
    }
}
