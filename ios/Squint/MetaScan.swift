import Foundation
import ImageIO

struct MetaResult {
    var generator = ""
    var camera = false
    var c2pa = false
    var sourceType = ""
    var notes: [String] = []

    var decisiveSynthetic: Bool { !generator.isEmpty || sourceType == "trainedalgorithmicmedia" }
    var verifiedCapture: Bool { c2pa && (camera || sourceType == "digitalcapture") }
}

enum MetaScan {
    private static let generators: [(String, String)] = [
        ("stable diffusion", "stable[\\s_-]?diffusion|sd[-_ ]?xl|automatic1111|comfyui|invokeai|novelai"),
        ("midjourney", "midjourney"),
        ("dall-e", "dall[\\s·.-]?e|openai"),
        ("adobe firefly", "firefly|adobe\\s+generative|generative\\s+fill"),
        ("google imagen", "imagen|gemini|synthid|nano\\s*banana"),
        ("flux", "black[\\s-]?forest[\\s-]?labs|\\bflux\\b"),
        ("ideogram", "ideogram"),
        ("leonardo", "leonardo\\.ai"),
    ]
    private static let cameras = "apple|samsung|google|sony|canon|nikon|leica|fujifilm|olympus|panasonic|xiaomi|oneplus|huawei|motorola|nothing|ricoh|hasselblad|dji|gopro"

    static func scan(_ data: Data) -> MetaResult {
        var r = MetaResult()
        var hay = ""
        let bytes = [UInt8](data)
        if bytes.count > 8, bytes[0] == 0x89, bytes[1] == 0x50 {
            for (kind, body) in pngChunks(bytes) {
                if kind == "tEXt" || kind == "iTXt" || kind == "zTXt" {
                    let key = String(decoding: body.prefix { $0 != 0 }, as: UTF8.self).lowercased()
                    let text = kind == "tEXt" ? String(decoding: body, as: UTF8.self).lowercased() : key
                    hay += key + "=" + text + " "
                    if ["parameters", "prompt", "workflow", "sd-metadata", "invokeai_metadata"].contains(key) {
                        r.notes.append("png carries a generation prompt block")
                    }
                }
                if kind == "caBX" || String(decoding: body.prefix(64), as: UTF8.self).contains("c2pa") { r.c2pa = true }
            }
        } else if bytes.count > 4, bytes[0] == 0xFF, bytes[1] == 0xD8 {
            for seg in jpegSegments(bytes) {
                let s = String(decoding: seg, as: UTF8.self).lowercased()
                let head = String(s.prefix(200))
                if seg.starts(with: Array("Exif".utf8)) { hay += s + " " }
                if head.contains("c2pa") || head.contains("jumb") { r.c2pa = true; hay += s + " " }
                if head.contains("ns.adobe.com/xap") {
                    hay += s + " "
                    if s.contains("trainedalgorithmicmedia") { r.sourceType = "trainedalgorithmicmedia" }
                    else if s.contains("digitalcapture") { r.sourceType = "digitalcapture" }
                }
            }
        }
        if let src = CGImageSourceCreateWithData(data as CFData, nil), let props = CGImageSourceCopyPropertiesAtIndex(src, 0, nil) as? [CFString: Any] {
            let tiff = props[kCGImagePropertyTIFFDictionary] as? [CFString: Any] ?? [:]
            let make = (tiff[kCGImagePropertyTIFFMake] as? String ?? "").lowercased()
            let software = (tiff[kCGImagePropertyTIFFSoftware] as? String ?? "").lowercased()
            hay += " make=" + make + " software=" + software + " "
            if make.range(of: cameras, options: .regularExpression) != nil || software.range(of: cameras, options: .regularExpression) != nil { r.camera = true }
        }
        if hay.contains("c2pa.created") || hay.contains("c2pa.actions") { r.c2pa = true }
        if hay.contains("trainedalgorithmicmedia") { r.sourceType = "trainedalgorithmicmedia" }
        for (name, pattern) in generators where hay.range(of: pattern, options: .regularExpression) != nil {
            r.generator = name
            break
        }
        if !r.generator.isEmpty { r.notes.append("metadata names \(r.generator)") }
        if r.sourceType == "trainedalgorithmicmedia" { r.notes.append("iptc digital source type says trained algorithmic media") }
        if r.c2pa { r.notes.append("content credentials manifest present") }
        if r.sourceType == "digitalcapture" { r.notes.append("iptc digital source type says camera capture") }
        return r
    }

    private static func pngChunks(_ b: [UInt8]) -> [(String, [UInt8])] {
        var out: [(String, [UInt8])] = []
        var pos = 8
        while pos + 8 <= b.count {
            let len = Int(b[pos]) << 24 | Int(b[pos + 1]) << 16 | Int(b[pos + 2]) << 8 | Int(b[pos + 3])
            guard len >= 0, pos + 12 + len <= b.count else { break }
            let kind = String(decoding: b[(pos + 4)..<(pos + 8)], as: UTF8.self)
            out.append((kind, Array(b[(pos + 8)..<(pos + 8 + len)])))
            pos += 12 + len
            if kind == "IEND" { break }
        }
        return out
    }

    private static func jpegSegments(_ b: [UInt8]) -> [[UInt8]] {
        var out: [[UInt8]] = []
        var pos = 2
        while pos + 4 <= b.count {
            if b[pos] != 0xFF { pos += 1; continue }
            let marker = Int(b[pos + 1])
            if marker == 0xD8 || marker == 0x01 || (0xD0...0xD7).contains(marker) { pos += 2; continue }
            if marker == 0xDA || marker == 0xD9 { break }
            let len = Int(b[pos + 2]) << 8 | Int(b[pos + 3])
            guard len >= 2, pos + 2 + len <= b.count else { break }
            if marker == 0xE1 || marker == 0xEB || marker == 0xFE { out.append(Array(b[(pos + 4)..<(pos + 2 + len)])) }
            pos += 2 + len
        }
        return out
    }
}
