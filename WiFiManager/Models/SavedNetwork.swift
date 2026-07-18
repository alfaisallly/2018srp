import Foundation

/// A Wi‑Fi network whose password was saved by the user inside this app.
struct SavedNetwork: Identifiable, Codable, Equatable {
    let id: UUID
    var ssid: String
    var password: String
    var notes: String
    var createdAt: Date
    var updatedAt: Date

    init(
        id: UUID = UUID(),
        ssid: String,
        password: String,
        notes: String = "",
        createdAt: Date = Date(),
        updatedAt: Date = Date()
    ) {
        self.id = id
        self.ssid = ssid
        self.password = password
        self.notes = notes
        self.createdAt = createdAt
        self.updatedAt = updatedAt
    }
}
