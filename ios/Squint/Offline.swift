import Foundation

enum Offline {
    private static let lines: [String: [String: String]] = [
        "en": ["likely_synthetic": "Likely AI.", "unclear": "Can't tell from this.", "verified_capture": "Camera verified by content credentials.", "device_only": "Checked on the phone only, no connection.", "metadata": "The file itself says it was generated."],
        "es": ["likely_synthetic": "Probablemente hecho con IA.", "unclear": "No se puede saber con esto.", "verified_capture": "Cámara verificada por credenciales de contenido.", "device_only": "Revisado solo en el teléfono, sin conexión.", "metadata": "El propio archivo dice que fue generado."],
        "pt": ["likely_synthetic": "Provavelmente feito por IA.", "unclear": "Não dá para saber com isso.", "verified_capture": "Câmera verificada por credenciais de conteúdo.", "device_only": "Verificado só no celular, sem conexão.", "metadata": "O próprio arquivo diz que foi gerado."],
        "hi": ["likely_synthetic": "शायद AI से बना है।", "unclear": "इससे बताना मुश्किल है।", "verified_capture": "कैमरे से लिया गया, कंटेंट क्रेडेंशियल से सत्यापित।", "device_only": "सिर्फ़ फ़ोन पर जांचा गया, कनेक्शन नहीं था।", "metadata": "फ़ाइल खुद कहती है कि यह जनरेट की गई है।"],
    ]
    private static let headlines = ["likely_synthetic": "Likely AI-made", "unclear": "Can't tell from this", "verified_capture": "Camera-verified capture"]
    private static let haptics: [String: ([Int], [Int], String)] = [
        "likely_synthetic": ([0, 650], [0, 255], "one long buzz"),
        "unclear": ([0, 70, 70, 70, 70, 70], [0, 200, 0, 200, 0, 200], "three quick taps"),
        "verified_capture": ([0, 90, 80, 380], [0, 140, 0, 255], "short then long"),
    ]

    static func verdict(for data: Data?) -> Verdict {
        let lang = Settings.lang
        let l = lines[lang] ?? lines["en"]!
        var tier = "unclear"
        var p = 0.5
        var evidence: [String] = []
        if let data {
            let m = MetaScan.scan(data)
            if m.decisiveSynthetic { tier = "likely_synthetic"; p = 0.95; evidence = m.notes }
            else if m.verifiedCapture { tier = "verified_capture"; p = 0.05; evidence = ["content credentials from a camera capture"] }
        }
        var say = l[tier] ?? l["unclear"]!
        if tier == "likely_synthetic" { say += " " + (l["metadata"] ?? "") }
        say += " " + (l["device_only"] ?? "")
        let h = haptics[tier]!
        return Verdict(checkId: "local-\(UUID().uuidString.prefix(8))", kind: "image", tier: tier, p: p, confidence: tier == "unclear" ? "low" : "medium",
                       haptic: Haptic(pattern: h.0, amplitudes: h.1, label: h.2), say: say, headline: headlines[tier] ?? "", evidence: evidence,
                       seenBefore: nil, phash: nil, quick: true, decisive: true, feedbackRecorded: false)
    }
}
