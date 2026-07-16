import Foundation
import SystemConfiguration.CaptiveNetwork
import Network

/// Reads the currently connected Wi‑Fi network name.
///
/// Apple does **not** allow third‑party apps to:
/// - Scan all nearby Wi‑Fi networks
/// - Read passwords saved in iOS Settings / Keychain
final class WiFiScannerService: ObservableObject {
    @Published private(set) var currentNetwork: WiFiNetwork?
    @Published private(set) var isRefreshing = false
    @Published private(set) var lastError: String?
    @Published private(set) var isConnectedToInternet = false

    private let monitor = NWPathMonitor(requiredInterfaceType: .wifi)
    private let monitorQueue = DispatchQueue(label: "com.wifimanager.monitor")

    init() {
        startMonitoring()
    }

    deinit {
        monitor.cancel()
    }

    func refreshCurrentNetwork(isLocationAuthorized: Bool) {
        isRefreshing = true
        lastError = nil
        defer { isRefreshing = false }

        guard isLocationAuthorized else {
            lastError = "يلزم إذن الموقع لقراءة اسم شبكة Wi‑Fi المتصلة."
            currentNetwork = nil
            return
        }

        guard let interfaces = CNCopySupportedInterfaces() as? [String] else {
            lastError = "لا توجد واجهة Wi‑Fi متاحة."
            currentNetwork = nil
            return
        }

        for interface in interfaces {
            guard
                let info = CNCopyCurrentNetworkInfo(interface as CFString) as? [String: AnyObject],
                let ssid = info[kCNNetworkInfoKeySSID as String] as? String,
                !ssid.isEmpty
            else { continue }

            let bssid = info[kCNNetworkInfoKeyBSSID as String] as? String
            currentNetwork = WiFiNetwork(ssid: ssid, bssid: bssid, scannedAt: Date())
            return
        }

        if isConnectedToInternet {
            lastError = "متصل بالإنترنت لكن اسم الشبكة غير متاح (قد تكون VPN أو Hotspot)."
        } else {
            lastError = "غير متصل بشبكة Wi‑Fi حالياً."
        }
        currentNetwork = nil
    }

    private func startMonitoring() {
        monitor.pathUpdateHandler = { [weak self] path in
            DispatchQueue.main.async {
                self?.isConnectedToInternet = path.status == .satisfied
            }
        }
        monitor.start(queue: monitorQueue)
    }
}
