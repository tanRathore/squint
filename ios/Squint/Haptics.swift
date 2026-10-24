import CoreHaptics
import UIKit

final class Haptics {
    static let shared = Haptics()
    private var engine: CHHapticEngine?

    private init() {
        guard CHHapticEngine.capabilitiesForHardware().supportsHaptics else { return }
        engine = try? CHHapticEngine()
        engine?.resetHandler = { [weak self] in try? self?.engine?.start() }
        try? engine?.start()
    }

    func play(pattern: [Int], amplitudes: [Int]) {
        guard let engine, !pattern.isEmpty else { fallback(pattern: pattern); return }
        var events: [CHHapticEvent] = []
        var t: TimeInterval = 0
        for (i, ms) in pattern.enumerated() {
            let dur = TimeInterval(ms) / 1000
            let amp = Float(amplitudes.indices.contains(i) ? amplitudes[i] : 0) / 255
            if amp > 0 {
                events.append(CHHapticEvent(
                    eventType: .hapticContinuous,
                    parameters: [
                        CHHapticEventParameter(parameterID: .hapticIntensity, value: amp),
                        CHHapticEventParameter(parameterID: .hapticSharpness, value: dur > 0.3 ? 0.35 : 0.7),
                    ],
                    relativeTime: t,
                    duration: dur
                ))
            }
            t += dur
        }
        do {
            let p = try CHHapticPattern(events: events, parameters: [])
            let player = try engine.makePlayer(with: p)
            try engine.start()
            try player.start(atTime: CHHapticTimeImmediate)
        } catch {
            fallback(pattern: pattern)
        }
    }

    func ack() { play(pattern: [0, 25], amplitudes: [0, 90]) }

    func thinking() { play(pattern: [0, 18, 120, 18], amplitudes: [0, 60, 0, 60]) }

    func failed() { play(pattern: [0, 40, 70, 40, 70, 40, 70, 40], amplitudes: [0, 120, 0, 120, 0, 120, 0, 120]) }

    private func fallback(pattern: [Int]) {
        let gen = UINotificationFeedbackGenerator()
        gen.prepare()
        let long = pattern.contains { $0 >= 400 }
        gen.notificationOccurred(long ? .warning : .success)
    }
}
