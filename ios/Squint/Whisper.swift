import AVFoundation

final class Whisper {
    static let shared = Whisper()
    private let synth = AVSpeechSynthesizer()

    func say(_ text: String) {
        guard Settings.speak, !text.isEmpty else { return }
        let session = AVAudioSession.sharedInstance()
        try? session.setCategory(.playback, mode: .voicePrompt, options: [.duckOthers, .interruptSpokenAudioAndMixWithOthers])
        try? session.setActive(true)
        let u = AVSpeechUtterance(string: text)
        u.rate = AVSpeechUtteranceDefaultSpeechRate * 1.05
        u.volume = 0.6
        u.prefersAssistiveTechnologySettings = false
        synth.speak(u)
    }
}
