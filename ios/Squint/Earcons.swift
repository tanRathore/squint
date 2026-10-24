import AVFoundation

final class Earcons {
    static let shared = Earcons()
    private var player: AVAudioPlayer?

    func play(pattern: [Int], amplitudes: [Int]) {
        guard Settings.earcons, !pattern.isEmpty else { return }
        let rate = 22050.0
        var samples: [Int16] = []
        let long = pattern.contains { $0 >= 400 }
        for (i, ms) in pattern.enumerated() {
            let n = Int(rate * Double(ms) / 1000)
            let amp = i < amplitudes.count ? amplitudes[i] : 0
            if amp == 0 {
                samples.append(contentsOf: [Int16](repeating: 0, count: n))
                continue
            }
            let freq = long && ms >= 400 ? 392.0 : 784.0
            let gain = 0.25 + 0.35 * Double(amp) / 255
            let fade = min(n / 6, Int(rate / 50))
            for j in 0..<n {
                let env = j < fade ? Double(j) / Double(fade) : (j > n - fade ? Double(n - j) / Double(fade) : 1)
                samples.append(Int16(sin(2 * .pi * freq * Double(j) / rate) * 32767 * gain * env))
            }
        }
        var data = Data()
        let byteCount = samples.count * 2
        func le32(_ v: UInt32) -> [UInt8] { [UInt8(v & 0xff), UInt8((v >> 8) & 0xff), UInt8((v >> 16) & 0xff), UInt8((v >> 24) & 0xff)] }
        func le16(_ v: UInt16) -> [UInt8] { [UInt8(v & 0xff), UInt8((v >> 8) & 0xff)] }
        data.append(contentsOf: Array("RIFF".utf8)); data.append(contentsOf: le32(UInt32(36 + byteCount))); data.append(contentsOf: Array("WAVE".utf8))
        data.append(contentsOf: Array("fmt ".utf8)); data.append(contentsOf: le32(16)); data.append(contentsOf: le16(1)); data.append(contentsOf: le16(1))
        data.append(contentsOf: le32(UInt32(rate))); data.append(contentsOf: le32(UInt32(rate * 2))); data.append(contentsOf: le16(2)); data.append(contentsOf: le16(16))
        data.append(contentsOf: Array("data".utf8)); data.append(contentsOf: le32(UInt32(byteCount)))
        samples.withUnsafeBufferPointer { data.append(Data(buffer: $0)) }
        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .default, options: [.duckOthers])
        try? AVAudioSession.sharedInstance().setActive(true)
        player = try? AVAudioPlayer(data: data)
        player?.volume = 0.7
        player?.play()
    }
}
