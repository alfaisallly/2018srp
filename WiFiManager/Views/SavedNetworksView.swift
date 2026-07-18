import SwiftUI

struct SavedNetworksView: View {
    @EnvironmentObject private var networkStore: NetworkStore
    @State private var showAddSheet = false
    @State private var searchText = ""

    private var filteredNetworks: [SavedNetwork] {
        guard !searchText.isEmpty else { return networkStore.networks }
        return networkStore.networks.filter {
            $0.ssid.localizedCaseInsensitiveContains(searchText) ||
            $0.notes.localizedCaseInsensitiveContains(searchText)
        }
    }

    var body: some View {
        NavigationStack {
            Group {
                if networkStore.networks.isEmpty {
                    ContentUnavailableView {
                        Label("لا توجد شبكات محفوظة", systemImage: "key.slash")
                    } description: {
                        Text("احفظ كلمات سر شبكاتك هنا لتجدها بسرعة لاحقاً.")
                    } actions: {
                        Button("إضافة شبكة") {
                            showAddSheet = true
                        }
                        .buttonStyle(.borderedProminent)
                    }
                } else {
                    List {
                        ForEach(filteredNetworks) { network in
                            NavigationLink {
                                NetworkDetailView(network: network)
                            } label: {
                                NetworkRowView(
                                    ssid: network.ssid,
                                    subtitle: network.notes.isEmpty ? "بدون ملاحظات" : network.notes,
                                    icon: "key.fill",
                                    tint: .blue
                                )
                            }
                        }
                        .onDelete(perform: deleteNetworks)
                    }
                    .searchable(text: $searchText, prompt: "بحث عن شبكة")
                }
            }
            .navigationTitle("كلمات السر")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button {
                        showAddSheet = true
                    } label: {
                        Image(systemName: "plus")
                    }
                }
            }
            .sheet(isPresented: $showAddSheet) {
                AddNetworkView()
            }
        }
    }

    private func deleteNetworks(at offsets: IndexSet) {
        let ids = offsets.map { filteredNetworks[$0].id }
        let storeOffsets = IndexSet(
            networkStore.networks.enumerated().compactMap { index, network in
                ids.contains(network.id) ? index : nil
            }
        )

        try? networkStore.deleteNetwork(at: storeOffsets)
    }
}

struct NetworkRowView: View {
    let ssid: String
    let subtitle: String
    let icon: String
    let tint: Color

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .foregroundStyle(tint)
                .frame(width: 28)

            VStack(alignment: .leading, spacing: 2) {
                Text(ssid)
                    .font(.headline)
                Text(subtitle)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
        }
        .padding(.vertical, 2)
    }
}

#Preview {
    SavedNetworksView()
        .environmentObject(NetworkStore())
        .environment(\.layoutDirection, .rightToLeft)
}
