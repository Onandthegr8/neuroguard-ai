import Foundation

/// AppGroupReader
///
/// Called from the main Flutter app (via MethodChannel) to read any keystroke
/// sessions that the keyboard extension wrote to the shared App Group container.
/// Sessions are consumed (removed) after being read to avoid double-uploading.

class AppGroupReader {
    private let appGroupId = "group.com.neuroguard.app"
    private let key        = "pending_keystroke_sessions"

    func consumePendingSessions() -> [[String: Any]] {
        guard let defaults = UserDefaults(suiteName: appGroupId) else { return [] }
        let sessions = defaults.array(forKey: key) as? [[String: Any]] ?? []
        defaults.removeObject(forKey: key)
        defaults.synchronize()
        return sessions
    }
}
