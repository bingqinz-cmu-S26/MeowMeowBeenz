import SwiftUI

struct ChatView: View {
    @Environment(AppModel.self) private var app
    @State private var input = ""

    private let prompts = [
        "How are the cats today?",
        "Should I worry?",
        "What was the last vocalization?"
    ]

    var body: some View {
        NavigationStack {
            ScrollViewReader { proxy in
                ScrollView {
                    VStack(alignment: .leading, spacing: 10) {
                        ForEach(app.chat) { message in
                            MessageBubble(message: message).id(message.id)
                        }
                        if app.isSending {
                            ProgressView().padding(.leading, 4)
                        }
                    }
                    .padding()
                }
                .onChange(of: app.chat.count) {
                    if let last = app.chat.last { withAnimation { proxy.scrollTo(last.id, anchor: .bottom) } }
                }
            }
            .navigationTitle("Chat")
            .safeAreaInset(edge: .bottom) { inputBar }
        }
    }

    private var inputBar: some View {
        VStack(spacing: 8) {
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(prompts, id: \.self) { prompt in
                        Button(prompt) { send(prompt) }
                            .buttonStyle(.bordered)
                            .controlSize(.small)
                    }
                }
                .padding(.horizontal)
            }
            HStack(spacing: 8) {
                TextField("Ask Beenz", text: $input)
                    .textFieldStyle(.roundedBorder)
                    .onSubmit { send(input) }
                Button {
                    send(input)
                } label: {
                    Image(systemName: "arrow.up.circle.fill").font(.title2)
                }
                .disabled(input.trimmingCharacters(in: .whitespaces).isEmpty || app.isSending)
            }
            .padding(.horizontal)
            .padding(.bottom, 6)
        }
        .background(.bar)
    }

    private func send(_ text: String) {
        let question = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !question.isEmpty else { return }
        input = ""
        Task { await app.sendMessage(question) }
    }
}

private struct MessageBubble: View {
    let message: ChatMessage

    var body: some View {
        HStack {
            if message.role == .owner { Spacer(minLength: 40) }
            VStack(alignment: .leading, spacing: 4) {
                Text(message.text)
                if let provider = message.provider {
                    Text(provider.uppercased())
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }
            .padding(10)
            .background(
                message.role == .owner ? Color.accentColor.opacity(0.18) : Color(.secondarySystemBackground),
                in: RoundedRectangle(cornerRadius: 12)
            )
            if message.role == .assistant { Spacer(minLength: 40) }
        }
    }
}
