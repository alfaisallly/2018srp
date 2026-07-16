import Foundation

/// Represents the currently connected Wi‑Fi network (SSID only — iOS does not expose passwords).
struct WiFiNetwork: Identifiable, Equatable {
    let id = UUID()
    let ssid: String
    let bssid: String?
    let scannedAt: Date

    var displayName: String {
        ssid.isEmpty ? "شبكة غير معروفة" : ssid
    }
}
