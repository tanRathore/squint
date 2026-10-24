import AppIntents
import UIKit

enum Deliver {
    static func verdict(_ o: Outcome) {
        Haptics.shared.play(pattern: o.verdict.haptic.pattern, amplitudes: o.verdict.haptic.amplitudes)
        Earcons.shared.play(pattern: o.verdict.haptic.pattern, amplitudes: o.verdict.haptic.amplitudes)
        Whisper.shared.say(o.verdict.say)
    }

    static func failed(_ line: String = "Couldn't reach squint.") {
        Haptics.shared.failed()
        Whisper.shared.say(line)
    }
}

struct CheckImageIntent: AppIntent {
    static var title: LocalizedStringResource = "Check with squint"
    static var description = IntentDescription("Tells you whether an image looks machine made, with a buzz and a short spoken line. Nothing is stored.")
    static var openAppWhenRun = false

    @Parameter(title: "Image", supportedTypeIdentifiers: ["public.image"], inputConnectionBehavior: .connectToPreviousIntentResult)
    var image: IntentFile

    @Parameter(title: "Source", default: "shortcut")
    var source: String

    static var parameterSummary: some ParameterSummary {
        Summary("Check \(\.$image) with squint")
    }

    func perform() async throws -> some IntentResult & ReturnsValue<String> & ProvidesDialog {
        Haptics.shared.ack()
        guard let ui = UIImage(data: image.data) else {
            Haptics.shared.failed()
            return .result(value: "unreadable", dialog: "That wasn't an image I could read.")
        }
        let thinking = Task {
            guard (try? await Task.sleep(nanoseconds: 1_600_000_000)) != nil, !Task.isCancelled else { return }
            Haptics.shared.thinking()
        }
        let out = await SquintClient().screenFlow(image: ui, app: source, trigger: "action_button") { q in
            if let n = q.seenBefore?.sightings, n >= 2 { Haptics.shared.ack() }
        }
        thinking.cancel()
        guard let out else {
            Deliver.failed()
            return .result(value: "error", dialog: "Couldn't reach squint.")
        }
        Deliver.verdict(out)
        return .result(value: out.verdict.tier, dialog: IntentDialog(stringLiteral: out.verdict.say))
    }
}

struct CheckTextIntent: AppIntent {
    static var title: LocalizedStringResource = "Check text with squint"
    static var description = IntentDescription("Reads a chunk of text and says whether it looks machine written or like a scam.")
    static var openAppWhenRun = false

    @Parameter(title: "Text", inputConnectionBehavior: .connectToPreviousIntentResult)
    var text: String

    func perform() async throws -> some IntentResult & ReturnsValue<String> & ProvidesDialog {
        Haptics.shared.ack()
        guard let out = await SquintClient().check(text: text, app: "shortcut") else {
            Deliver.failed()
            return .result(value: "error", dialog: "Couldn't reach squint.")
        }
        Deliver.verdict(out)
        return .result(value: out.verdict.tier, dialog: IntentDialog(stringLiteral: out.verdict.say))
    }
}

struct CheckFileIntent: AppIntent {
    static var title: LocalizedStringResource = "Check a clip with squint"
    static var description = IntentDescription("Video or audio. Fingerprints the clip, checks it, buzzes the answer.")
    static var openAppWhenRun = false

    @Parameter(title: "File", supportedTypeIdentifiers: ["public.movie", "public.audio"], inputConnectionBehavior: .connectToPreviousIntentResult)
    var file: IntentFile

    func perform() async throws -> some IntentResult & ReturnsValue<String> & ProvidesDialog {
        Haptics.shared.ack()
        let name = file.filename
        let mime = name.lowercased().hasSuffix(".mp4") || name.lowercased().hasSuffix(".mov") ? "video/mp4" : "audio/mp4"
        guard let out = await SquintClient().check(fileData: file.data, name: name, mime: mime, app: "shortcut") else {
            Deliver.failed()
            return .result(value: "error", dialog: "Couldn't reach squint.")
        }
        Deliver.verdict(out)
        return .result(value: out.verdict.tier, dialog: IntentDialog(stringLiteral: out.verdict.say))
    }
}
