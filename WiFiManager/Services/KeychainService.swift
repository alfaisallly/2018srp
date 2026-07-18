import Foundation
import Security

enum KeychainError: LocalizedError {
    case encodingFailed
    case saveFailed(OSStatus)
    case readFailed(OSStatus)
    case deleteFailed(OSStatus)
    case notFound

    var errorDescription: String? {
        switch self {
        case .encodingFailed:
            return "تعذّر ترميز البيانات."
        case .saveFailed(let status):
            return "فشل الحفظ في Keychain (رمز: \(status))."
        case .readFailed(let status):
            return "فشل القراءة من Keychain (رمز: \(status))."
        case .deleteFailed(let status):
            return "فشل الحذف من Keychain (رمز: \(status))."
        case .notFound:
            return "لم يتم العثور على البيانات."
        }
    }
}

/// Stores Wi‑Fi passwords securely in the iOS Keychain.
final class KeychainService {
    static let shared = KeychainService()

    private let serviceName = "com.wifimanager.passwords"

    private init() {}

    func savePassword(_ password: String, for networkID: UUID) throws {
        let account = networkID.uuidString
        let data = Data(password.utf8)

        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: serviceName,
            kSecAttrAccount as String: account
        ]

        SecItemDelete(query as CFDictionary)

        var attributes = query
        attributes[kSecValueData as String] = data
        attributes[kSecAttrAccessible as String] = kSecAttrAccessibleWhenUnlockedThisDeviceOnly

        let status = SecItemAdd(attributes as CFDictionary, nil)
        guard status == errSecSuccess else {
            throw KeychainError.saveFailed(status)
        }
    }

    func readPassword(for networkID: UUID) throws -> String {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: serviceName,
            kSecAttrAccount as String: networkID.uuidString,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]

        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)

        guard status != errSecItemNotFound else { throw KeychainError.notFound }
        guard status == errSecSuccess else { throw KeychainError.readFailed(status) }
        guard let data = result as? Data, let password = String(data: data, encoding: .utf8) else {
            throw KeychainError.encodingFailed
        }

        return password
    }

    func deletePassword(for networkID: UUID) throws {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: serviceName,
            kSecAttrAccount as String: networkID.uuidString
        ]

        let status = SecItemDelete(query as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else {
            throw KeychainError.deleteFailed(status)
        }
    }
}
