import SwiftUI

struct CurrentNetworkView: View {
    @EnvironmentObject private var wifiScanner: WiFiScannerService
    @EnvironmentObject private var locationManager: LocationPermissionManager
    @EnvironmentObject private var networkStore: NetworkStore

    @State private var showAddSheet = false

    var body: some View {
        NavigationStack {
            List {
                Section {
                    if !locationManager.isAuthorized {
                        PermissionBannerView()
                    }

                    if let network = wifiScanner.currentNetwork {
                        NetworkRowView(
                            ssid: network.displayName,
                            subtitle: network.bssid ?? "بدون عنوان MAC",
                            icon: "wifi",
                            tint: .green
                        )

                        if let saved = networkStore.importFromCurrentNetwork(network) {
                            SavedPasswordPreviewView(password: saved.password)
                        } else {
                            Button {
                                showAddSheet = true
                            } label: {
                                Label("حفظ كلمة سر هذه الشبكة", systemImage: "plus.circle.fill")
                            }
                        }
                    } else {
                        ContentUnavailableView(
                            "لا توجد شبكة Wi‑Fi",
                            systemImage: "wifi.slash",
                            description: Text(wifiScanner.lastError ?? "اضغط «تحديث» بعد الاتصال بشبكة Wi‑Fi.")
                        )
                    }
                } header: {
                    Text("الشبكة المتصلة الآن")
                } footer: {
                    Text("iOS لا يسمح للتطبيقات بقراءة كلمات السر المحفوظة في النظام. يمكنك فقط رؤية اسم الشبكة الحالية وحفظ كلمات السر التي تُدخلها بنفسك.")
                }

                Section("حالة الاتصال") {
                    LabeledContent("Wi‑Fi") {
                        Text(wifiScanner.isConnectedToInternet ? "متصل" : "غير متصل")
                            .foregroundStyle(wifiScanner.isConnectedToInternet ? .green : .secondary)
                    }

                    if let scannedAt = wifiScanner.currentNetwork?.scannedAt {
                        LabeledContent("آخر فحص") {
                            Text(scannedAt, style: .time)
                        }
                    }
                }

                Section("ملاحظة مهمة") {
                    LimitationCardView()
                }
            }
            .navigationTitle("مدير Wi‑Fi")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("تحديث") {
                        refresh()
                    }
                    .disabled(wifiScanner.isRefreshing)
                }
            }
            .refreshable {
                refresh()
            }
            .onAppear {
                locationManager.requestPermission()
                refresh()
            }
            .sheet(isPresented: $showAddSheet) {
                if let network = wifiScanner.currentNetwork {
                    AddNetworkView(prefilledSSID: network.ssid)
                }
            }
        }
    }

    private func refresh() {
        wifiScanner.refreshCurrentNetwork(isLocationAuthorized: locationManager.isAuthorized)
    }
}

private struct PermissionBannerView: View {
    @EnvironmentObject private var locationManager: LocationPermissionManager

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("يلزم إذن الموقع", systemImage: "location.fill")
                .font(.headline)

            Text("Apple تطلب إذن الموقع لعرض اسم شبكة Wi‑Fi المتصلة.")
                .font(.subheadline)
                .foregroundStyle(.secondary)

            Button("منح الإذن") {
                locationManager.requestPermission()
            }
            .buttonStyle(.borderedProminent)
        }
        .padding(.vertical, 4)
    }
}

private struct SavedPasswordPreviewView: View {
    let password: String
    @State private var isVisible = false

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("كلمة السر المحفوظة في التطبيق")
                .font(.subheadline)
                .foregroundStyle(.secondary)

            HStack {
                Text(isVisible ? password : String(repeating: "•", count: max(password.count, 8)))
                    .font(.body.monospaced())
                    .textSelection(isVisible ? .enabled : .disabled)

                Spacer()

                Button {
                    isVisible.toggle()
                } label: {
                    Image(systemName: isVisible ? "eye.slash" : "eye")
                }
                .buttonStyle(.borderless)

                if isVisible {
                    ShareLink(item: password) {
                        Image(systemName: "square.and.arrow.up")
                    }
                    .buttonStyle(.borderless)
                }
            }
        }
    }
}

private struct LimitationCardView: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("قيود iOS الأمنية", systemImage: "lock.shield")
                .font(.headline)

            Text("لا يمكن لأي تطبيق من App Store:")
                .font(.subheadline)

            VStack(alignment: .leading, spacing: 4) {
                Text("• مسح جميع الشبكات المجاورة")
                Text("• قراءة كلمات السر المحفوظة في iOS")
                Text("• اختراق شبكات الآخرين")
            }
            .font(.footnote)
            .foregroundStyle(.secondary)
        }
        .padding(.vertical, 4)
    }
}

#Preview {
    CurrentNetworkView()
        .environmentObject(WiFiScannerService())
        .environmentObject(LocationPermissionManager())
        .environmentObject(NetworkStore())
        .environment(\.layoutDirection, .rightToLeft)
}
