import SwiftUI

//  مدير Wi‑Fi
//  © 2026 مهندس احمد ماجد — جميع حقوق التصميم والملكية محفوظة

@main
struct WiFiManagerApp: App {
    @StateObject private var networkStore = NetworkStore()
    @StateObject private var wifiScanner = WiFiScannerService()
    @StateObject private var locationManager = LocationPermissionManager()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(networkStore)
                .environmentObject(wifiScanner)
                .environmentObject(locationManager)
                .environment(\.layoutDirection, .rightToLeft)
        }
    }
}
