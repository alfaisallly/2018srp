import SwiftUI

struct NetworkDetailView: View {
    @EnvironmentObject private var networkStore: NetworkStore
    @Environment(\.dismiss) private var dismiss

    let network: SavedNetwork

    @State private var ssid: String
    @State private var password: String
    @State private var notes: String
    @State private var isPasswordVisible = false
    @State private var errorMessage: String?
    @State private var showSavedAlert = false

    init(network: SavedNetwork) {
        self.network = network
        _ssid = State(initialValue: network.ssid)
        _password = State(initialValue: network.password)
        _notes = State(initialValue: network.notes)
    }

    var body: some View {
        Form {
            Section("معلومات الشبكة") {
                TextField("اسم الشبكة (SSID)", text: $ssid)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()

                HStack {
                    Group {
                        if isPasswordVisible {
                            TextField("كلمة السر", text: $password)
                        } else {
                            SecureField("كلمة السر", text: $password)
                        }
                    }
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()

                    Button {
                        isPasswordVisible.toggle()
                    } label: {
                        Image(systemName: isPasswordVisible ? "eye.slash" : "eye")
                    }
                    .buttonStyle(.borderless)
                }

                TextField("ملاحظات", text: $notes, axis: .vertical)
                    .lineLimit(2...4)
            }

            Section {
                Button("حفظ التعديلات") {
                    saveChanges()
                }

                ShareLink(item: shareText) {
                    Label("مشاركة كلمة السر", systemImage: "square.and.arrow.up")
                }
            }

            if let errorMessage {
                Section {
                    Text(errorMessage)
                        .foregroundStyle(.red)
                }
            }
        }
        .navigationTitle(network.ssid)
        .navigationBarTitleDisplayMode(.inline)
        .alert("تم الحفظ", isPresented: $showSavedAlert) {
            Button("حسناً", role: .cancel) {}
        }
    }

    private var shareText: String {
        "شبكة: \(ssid)\nكلمة السر: \(password)"
    }

    private func saveChanges() {
        guard let index = networkStore.networks.firstIndex(where: { $0.id == network.id }) else { return }

        do {
            try networkStore.updateNetwork(at: index, password: password, notes: notes)
            showSavedAlert = true
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

#Preview {
    NavigationStack {
        NetworkDetailView(
            network: SavedNetwork(ssid: "HomeWiFi", password: "secret123", notes: "المنزل")
        )
    }
    .environmentObject(NetworkStore())
    .environment(\.layoutDirection, .rightToLeft)
}
