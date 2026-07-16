import SwiftUI

struct ContentView: View {
    var body: some View {
        TabView {
            CurrentNetworkView()
                .tabItem {
                    Label("الشبكة الحالية", systemImage: "wifi")
                }

            SavedNetworksView()
                .tabItem {
                    Label("كلمات السر", systemImage: "key.fill")
                }

            SettingsGuideView()
                .tabItem {
                    Label("دليل iOS", systemImage: "info.circle")
                }
        }
    }
}

#Preview {
    ContentView()
        .environmentObject(NetworkStore())
        .environmentObject(WiFiScannerService())
        .environmentObject(LocationPermissionManager())
        .environment(\.layoutDirection, .rightToLeft)
}
