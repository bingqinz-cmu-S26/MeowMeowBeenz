import SwiftUI

struct AccountView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss

    @State private var username = ""
    @State private var password = ""
    @State private var isRegister = false
    @State private var working = false

    // Add-cat fields
    @State private var catName = ""
    @State private var catBirthDate = Date()

    var body: some View {
        NavigationStack {
            Form {
                if app.isSignedIn, let user = app.user {
                    Section("Signed in") {
                        LabeledContent("User", value: user.displayName)
                        Button("Sign out", role: .destructive) { app.signOut() }
                    }

                    Section("Add a cat") {
                        TextField("Name", text: $catName)
                        DatePicker("Birth date", selection: $catBirthDate, displayedComponents: .date)
                        Button("Add cat") { addCat() }
                            .disabled(catName.trimmingCharacters(in: .whitespaces).isEmpty || working)
                    }
                } else {
                    Section(isRegister ? "Create account" : "Sign in") {
                        TextField("Username", text: $username)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                        SecureField("Password", text: $password)
                        Button(isRegister ? "Create account" : "Sign in") { authenticate() }
                            .disabled(username.isEmpty || password.isEmpty || working)
                    }
                    Section {
                        Button(isRegister ? "Have an account? Sign in" : "New here? Create an account") {
                            isRegister.toggle()
                        }
                        .font(.footnote)
                    }
                }

                Section("Server") {
                    TextField("API base URL", text: Binding(
                        get: { app.baseURLString },
                        set: { app.baseURLString = $0 }
                    ))
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                }

                if let error = app.errorMessage {
                    Section { Text(error).foregroundStyle(.red).font(.footnote) }
                }
            }
            .navigationTitle("Account")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) { Button("Done") { dismiss() } }
            }
            .overlay { if working { ProgressView() } }
        }
    }

    private func authenticate() {
        working = true
        Task {
            await app.signIn(username: username, password: password, isRegister: isRegister)
            working = false
            if app.isSignedIn { dismiss() }
        }
    }

    private func addCat() {
        working = true
        let iso = catBirthDate.formatted(.iso8601.year().month().day())
        Task {
            let ok = await app.addCat(name: catName, birthDate: iso, device: nil)
            working = false
            if ok { catName = "" }
        }
    }
}
