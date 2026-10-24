import Foundation

enum Settings {
    static let suite = UserDefaults(suiteName: "group.app.squint") ?? .standard

    static var server: String {
        get { suite.string(forKey: "server") ?? "https://squint.example.com" }
        set { suite.set(newValue.trimmingCharacters(in: CharacterSet(charactersIn: "/ ")), forKey: "server") }
    }

    static var speak: Bool {
        get { suite.object(forKey: "speak") as? Bool ?? true }
        set { suite.set(newValue, forKey: "speak") }
    }

    static var earcons: Bool {
        get { suite.object(forKey: "earcons") as? Bool ?? false }
        set { suite.set(newValue, forKey: "earcons") }
    }

    static var offline: Bool {
        get { suite.object(forKey: "offline") as? Bool ?? true }
        set { suite.set(newValue, forKey: "offline") }
    }

    static var lang: String {
        let code = String(Locale.preferredLanguages.first?.prefix(2) ?? "en").lowercased()
        return ["en", "es", "pt", "hi"].contains(code) ? code : "en"
    }

    static var deviceId: String {
        if let id = suite.string(forKey: "device_id") { return id }
        let fresh = UUID().uuidString
        suite.set(fresh, forKey: "device_id")
        return fresh
    }

    static func rotateId() {
        suite.set(UUID().uuidString, forKey: "device_id")
    }

    static func rememberLast(_ v: Verdict) {
        guard let ph = v.phash, !v.checkId.hasPrefix("local-") else { return }
        suite.set(["id": v.checkId, "phash": ph, "ts": Date().timeIntervalSince1970], forKey: "last")
    }

    static var last: (id: String, phash: String, ts: Double)? {
        guard let d = suite.dictionary(forKey: "last"), let id = d["id"] as? String, let ph = d["phash"] as? String, let ts = d["ts"] as? Double else { return nil }
        return (id, ph, ts)
    }

    static func remember(_ v: Verdict, app: String) {
        if v.feedbackRecorded { return }
        var rows = suite.array(forKey: "recent") as? [[String: Any]] ?? []
        rows.insert(["id": v.checkId, "headline": v.headline, "tier": v.tier, "app": app, "at": Date().timeIntervalSince1970], at: 0)
        suite.set(Array(rows.prefix(10)), forKey: "recent")
        rememberLast(v)
    }

    static var recent: [[String: Any]] {
        suite.array(forKey: "recent") as? [[String: Any]] ?? []
    }

    static var tutorialDone: Bool {
        get { suite.bool(forKey: "tutorial") }
        set { suite.set(newValue, forKey: "tutorial") }
    }
}
