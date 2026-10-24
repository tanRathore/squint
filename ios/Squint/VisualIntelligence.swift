import AppIntents
import UIKit

#if canImport(VisualIntelligence)
import VisualIntelligence

@available(iOS 26, *)
struct VerdictEntity: AppEntity {
    static var typeDisplayRepresentation: TypeDisplayRepresentation = "squint verdict"
    static var defaultQuery = VerdictQuery()

    var id: String
    var headline: String
    var say: String
    var tier: String

    var displayRepresentation: DisplayRepresentation {
        DisplayRepresentation(title: LocalizedStringResource(stringLiteral: headline), subtitle: LocalizedStringResource(stringLiteral: say), image: .init(systemName: tier == "likely_synthetic" ? "exclamationmark.triangle.fill" : (tier == "unclear" ? "questionmark.circle" : "checkmark.circle")))
    }
}

@available(iOS 26, *)
struct VerdictQuery: EntityQuery {
    func entities(for identifiers: [String]) async throws -> [VerdictEntity] {
        identifiers.compactMap { Recent.verdicts[$0] }
    }
}

@available(iOS 26, *)
enum Recent {
    static var verdicts: [String: VerdictEntity] = [:]
}

@available(iOS 26, *)
struct SquintVisualQuery: IntentValueQuery {
    func values(for input: SemanticContentDescriptor) async throws -> [VerdictEntity] {
        guard let buffer = input.pixelBuffer else { return [] }
        let ci = CIImage(cvPixelBuffer: buffer)
        let ctx = CIContext()
        guard let cg = ctx.createCGImage(ci, from: ci.extent) else { return [] }
        let ui = UIImage(cgImage: cg)
        Haptics.shared.ack()
        guard let out = await SquintClient().screenFlow(image: ui, app: "visual_intelligence", trigger: "screenshot") else { return [] }
        Deliver.verdict(out)
        let e = VerdictEntity(id: out.verdict.checkId, headline: out.verdict.headline, say: out.verdict.say, tier: out.verdict.tier)
        Recent.verdicts[e.id] = e
        return [e]
    }
}

@available(iOS 26, *)
struct OpenVerdictIntent: OpenIntent {
    static var title: LocalizedStringResource = "Show squint verdict"
    @Parameter(title: "Verdict") var target: VerdictEntity

    func perform() async throws -> some IntentResult {
        .result()
    }
}
#endif
