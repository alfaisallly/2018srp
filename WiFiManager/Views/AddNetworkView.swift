import SwiftUI

struct AddNetworkView: View {
    @EnvironmentObject private var networkStore: NetworkStore
    @Environment(\.dismiss) private var dismiss

    var prefilledSSID: String = ""

    @State private var ssid = ""
    @State private var password = ""
    @State private var notes = ""
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            Form {
                Section("بيانات الشبكة") {
                    TextField("اسم الشبكة (SSID)", text: $ssid)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()

                    SecureField("كلمة السر", text: $password)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()

                    TextField("ملاحظات (اختياري)", text: $notes, axis: .vertical)
                        .lineLimit(2...4)
                }

                Section {
                    Text("احفظ هنا كلمات السر التي تعرفها. التطبيق لا يستطيع استخراجها تلقائياً من iOS.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }

                if let errorMessage {
                    Section {
                        Text(errorMessage)
                            .foregroundStyle(.red)
                    }
                }
            }
            .navigationTitle("إضافة شبكة")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("إلغاء") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("حفظ") { save() }
                        .disabled(ssid.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || password.isEmpty)
                }
            }
            .onAppear {
                if ssid.isEmpty {
                    ssid = prefilledSSID
                }
            }
        }
    }

    private func save() {
        do {
            try networkStore.addNetwork(ssid: ssid, password: password, notes: notes)
            dismiss()
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

#Preview {
    AddNetworkView(prefilledSSID: "CafeWiFi")
        .environmentObject(NetworkStore())
        .environment(\.layoutDirection, .rightToLeft)
}
