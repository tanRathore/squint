import Foundation
import UIKit

enum SquintError: Error {
    case server(Int, String)
    case badImage
    case unreachable
}

struct Outcome {
    let verdict: Verdict
    var offline = false
}

struct SquintClient {
    let base: String
    let device: String

    init() {
        base = Settings.server
        device = Settings.deviceId
    }

    func screenFlow(image: UIImage, app: String, trigger: String, onQuick: ((Verdict) -> Void)? = nil) async -> Outcome? {
        let small = image.resized(maxSide: 720)
        guard let quickJpeg = small.jpegData(compressionQuality: 0.8) else { return nil }
        var fields = ["source_app": app, "trigger": trigger, "lang": Settings.lang]
        if let last = Settings.last {
            fields["prev_check"] = last.id
            fields["prev_phash"] = last.phash
            fields["prev_ts"] = String(last.ts)
        }
        do {
            let q = try await upload(path: "v1/quick", data: quickJpeg, name: "Screenshot.jpg", mime: "image/jpeg", fields: fields, app: app)
            if q.feedbackRecorded || q.decisive { return Outcome(verdict: q) }
            onQuick?(q)
        } catch SquintError.unreachable {
            return offline(nil)
        } catch {
        }
        let big = image.size.width > 1600 || image.size.height > 1600 ? image.resized(maxSide: 1600) : image
        guard let jpeg = big.jpegData(compressionQuality: 0.9) else { return nil }
        fields.removeValue(forKey: "prev_check"); fields.removeValue(forKey: "prev_phash"); fields.removeValue(forKey: "prev_ts")
        do {
            return Outcome(verdict: try await upload(path: "v1/check", data: jpeg, name: "Screenshot.jpg", mime: "image/jpeg", fields: fields, app: app))
        } catch SquintError.unreachable {
            return offline(nil)
        } catch {
            return nil
        }
    }

    func watch(image: UIImage) async -> Verdict? {
        guard let jpeg = image.resized(maxSide: 720).jpegData(compressionQuality: 0.8) else { return nil }
        return try? await upload(path: "v1/check", data: jpeg, name: "Screenshot.jpg", mime: "image/jpeg", fields: ["source_app": "watch", "trigger": "watch", "lang": Settings.lang], app: "watch")
    }

    func check(fileData: Data, name: String, mime: String, app: String) async -> Outcome? {
        do {
            return Outcome(verdict: try await upload(path: "v1/check", data: fileData, name: name, mime: mime, fields: ["source_app": app, "trigger": "share", "lang": Settings.lang], app: app))
        } catch SquintError.unreachable {
            return mime.hasPrefix("image/") ? offline(fileData) : nil
        } catch {
            return nil
        }
    }

    func check(text: String, app: String) async -> Outcome? {
        var req = URLRequest(url: URL(string: "\(base)/v1/check/text")!)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue(device, forHTTPHeaderField: "X-Device")
        req.setValue(Settings.lang, forHTTPHeaderField: "Accept-Language")
        req.httpBody = try? JSONSerialization.data(withJSONObject: ["text": text, "source_app": app, "lang": Settings.lang])
        return (try? await send(req, app: app)).map { Outcome(verdict: $0) }
    }

    private func offline(_ data: Data?) -> Outcome? {
        guard Settings.offline else { return nil }
        return Outcome(verdict: Offline.verdict(for: data), offline: true)
    }

    func registerPush(token: String) async {
        var req = URLRequest(url: URL(string: "\(base)/v1/push/register")!)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue(device, forHTTPHeaderField: "X-Device")
        req.httpBody = try? JSONSerialization.data(withJSONObject: ["token": token, "platform": "ios"])
        _ = try? await URLSession.shared.data(for: req)
    }

    func details(checkId: String) async -> Verdict? {
        if checkId.hasPrefix("local-") { return nil }
        guard let url = URL(string: "\(base)/v1/check/\(checkId)") else { return nil }
        var req = URLRequest(url: url)
        req.setValue(device, forHTTPHeaderField: "X-Device")
        guard let (data, resp) = try? await URLSession.shared.data(for: req), (resp as? HTTPURLResponse)?.statusCode == 200 else { return nil }
        return try? JSONDecoder().decode(Verdict.self, from: data)
    }

    func feedback(checkId: String, label: String) async {
        if checkId.hasPrefix("local-") { return }
        var req = URLRequest(url: URL(string: "\(base)/v1/feedback")!)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try? JSONSerialization.data(withJSONObject: ["check_id": checkId, "label": label])
        _ = try? await URLSession.shared.data(for: req)
    }

    private func upload(path: String, data: Data, name: String, mime: String, fields: [String: String], app: String) async throws -> Verdict {
        let boundary = "squint-\(UUID().uuidString)"
        var body = Data()
        for (k, v) in fields {
            body.append("--\(boundary)\r\nContent-Disposition: form-data; name=\"\(k)\"\r\n\r\n\(v)\r\n".data(using: .utf8)!)
        }
        body.append("--\(boundary)\r\nContent-Disposition: form-data; name=\"file\"; filename=\"\(name)\"\r\nContent-Type: \(mime)\r\n\r\n".data(using: .utf8)!)
        body.append(data)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)
        var req = URLRequest(url: URL(string: "\(base)/\(path)")!)
        req.httpMethod = "POST"
        req.timeoutInterval = path.hasSuffix("quick") ? 6 : 25
        req.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        req.setValue(device, forHTTPHeaderField: "X-Device")
        req.setValue(Settings.lang, forHTTPHeaderField: "Accept-Language")
        req.httpBody = body
        return try await send(req, app: app)
    }

    private func send(_ req: URLRequest, app: String) async throws -> Verdict {
        let data: Data
        let resp: URLResponse
        do {
            (data, resp) = try await URLSession.shared.data(for: req)
        } catch {
            throw SquintError.unreachable
        }
        let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
        guard (200..<300).contains(code) else {
            throw SquintError.server(code, String(data: data, encoding: .utf8) ?? "")
        }
        let v = try JSONDecoder().decode(Verdict.self, from: data)
        Settings.remember(v, app: app)
        return v
    }
}

extension UIImage {
    func resized(maxSide: CGFloat) -> UIImage {
        let longest = max(size.width, size.height)
        guard longest > maxSide else { return self }
        let scale = maxSide / longest
        let target = CGSize(width: size.width * scale, height: size.height * scale)
        let r = UIGraphicsImageRenderer(size: target)
        return r.image { _ in draw(in: CGRect(origin: .zero, size: target)) }
    }
}
