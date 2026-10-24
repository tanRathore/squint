import Foundation

struct Haptic: Decodable {
    let pattern: [Int]
    let amplitudes: [Int]
    let label: String
}

struct SeenBefore: Decodable {
    let sightings: Int
    let first_seen: String
}

struct Verdict: Decodable {
    let checkId: String
    let kind: String
    let tier: String
    let p: Double
    let confidence: String
    let haptic: Haptic
    let say: String
    let headline: String
    let evidence: [String]
    let seenBefore: SeenBefore?
    let phash: String?
    var quick: Bool = false
    var decisive: Bool = true
    var feedbackRecorded: Bool = false

    enum CodingKeys: String, CodingKey {
        case checkId = "check_id", kind, tier, p, confidence, haptic, say, headline, evidence, phash, quick, decisive
        case seenBefore = "seen_before"
        case feedbackRecorded = "feedback_recorded"
    }

    init(checkId: String, kind: String, tier: String, p: Double, confidence: String, haptic: Haptic, say: String, headline: String, evidence: [String], seenBefore: SeenBefore?, phash: String?, quick: Bool, decisive: Bool, feedbackRecorded: Bool) {
        self.checkId = checkId; self.kind = kind; self.tier = tier; self.p = p; self.confidence = confidence; self.haptic = haptic
        self.say = say; self.headline = headline; self.evidence = evidence; self.seenBefore = seenBefore; self.phash = phash
        self.quick = quick; self.decisive = decisive; self.feedbackRecorded = feedbackRecorded
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        checkId = try c.decode(String.self, forKey: .checkId)
        kind = try c.decode(String.self, forKey: .kind)
        tier = try c.decode(String.self, forKey: .tier)
        p = try c.decode(Double.self, forKey: .p)
        confidence = try c.decodeIfPresent(String.self, forKey: .confidence) ?? "low"
        haptic = try c.decode(Haptic.self, forKey: .haptic)
        say = try c.decodeIfPresent(String.self, forKey: .say) ?? ""
        headline = try c.decodeIfPresent(String.self, forKey: .headline) ?? ""
        evidence = try c.decodeIfPresent([String].self, forKey: .evidence) ?? []
        seenBefore = try c.decodeIfPresent(SeenBefore.self, forKey: .seenBefore)
        phash = try c.decodeIfPresent(String.self, forKey: .phash)
        quick = try c.decodeIfPresent(Bool.self, forKey: .quick) ?? false
        decisive = try c.decodeIfPresent(Bool.self, forKey: .decisive) ?? true
        feedbackRecorded = try c.decodeIfPresent(Bool.self, forKey: .feedbackRecorded) ?? false
    }
}
