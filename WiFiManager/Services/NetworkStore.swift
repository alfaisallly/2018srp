import Foundation
import Combine

/// Persists network metadata locally; passwords live in Keychain.
final class NetworkStore: ObservableObject {
    @Published private(set) var networks: [SavedNetwork] = []

    private let keychain = KeychainService.shared
    private let metadataKey = "saved_wifi_networks_metadata"
    private let defaults = UserDefaults.standard

    init() {
        loadMetadata()
    }

    func addNetwork(ssid: String, password: String, notes: String = "") throws {
        let trimmedSSID = ssid.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedSSID.isEmpty else { return }

        if let index = networks.firstIndex(where: { $0.ssid.caseInsensitiveCompare(trimmedSSID) == .orderedSame }) {
            try updateNetwork(at: index, password: password, notes: notes)
            return
        }

        let network = SavedNetwork(ssid: trimmedSSID, password: "", notes: notes)
        try keychain.savePassword(password, for: network.id)

        var stored = network
        stored.password = password
        networks.insert(stored, at: 0)
        saveMetadata()
    }

    func updateNetwork(at index: Int, password: String, notes: String) throws {
        guard networks.indices.contains(index) else { return }

        try keychain.savePassword(password, for: networks[index].id)
        networks[index].password = password
        networks[index].notes = notes
        networks[index].updatedAt = Date()
        saveMetadata()
    }

    func deleteNetwork(at offsets: IndexSet) throws {
        for index in offsets {
            try keychain.deletePassword(for: networks[index].id)
        }
        networks.remove(atOffsets: offsets)
        saveMetadata()
    }

    func password(for network: SavedNetwork) throws -> String {
        try keychain.readPassword(for: network.id)
    }

    func importFromCurrentNetwork(_ network: WiFiNetwork) -> SavedNetwork? {
        networks.first { $0.ssid.caseInsensitiveCompare(network.ssid) == .orderedSame }
    }

    private struct Metadata: Codable {
        let id: UUID
        let ssid: String
        let notes: String
        let createdAt: Date
        let updatedAt: Date
    }

    private func loadMetadata() {
        guard
            let data = defaults.data(forKey: metadataKey),
            let items = try? JSONDecoder().decode([Metadata].self, from: data)
        else { return }

        networks = items.compactMap { item in
            guard let password = try? keychain.readPassword(for: item.id) else { return nil }
            return SavedNetwork(
                id: item.id,
                ssid: item.ssid,
                password: password,
                notes: item.notes,
                createdAt: item.createdAt,
                updatedAt: item.updatedAt
            )
        }
    }

    private func saveMetadata() {
        let items = networks.map {
            Metadata(
                id: $0.id,
                ssid: $0.ssid,
                notes: $0.notes,
                createdAt: $0.createdAt,
                updatedAt: $0.updatedAt
            )
        }

        if let data = try? JSONEncoder().encode(items) {
            defaults.set(data, forKey: metadataKey)
        }
    }
}
