import UIKit
import UniformTypeIdentifiers

final class ShareViewController: UIViewController {
    private let label = UILabel()

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .clear
        label.text = "squint is looking…"
        label.textColor = .white
        label.font = .systemFont(ofSize: 15, weight: .medium)
        label.backgroundColor = UIColor.black.withAlphaComponent(0.75)
        label.textAlignment = .center
        label.layer.cornerRadius = 14
        label.clipsToBounds = true
        label.isAccessibilityElement = true
        label.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(label)
        NSLayoutConstraint.activate([
            label.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            label.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor, constant: -40),
            label.widthAnchor.constraint(equalToConstant: 260),
            label.heightAnchor.constraint(equalToConstant: 44),
        ])
        Haptics.shared.ack()
        Task { await self.run() }
    }

    private func run() async {
        guard let item = (extensionContext?.inputItems as? [NSExtensionItem])?.first,
              let provider = item.attachments?.first else {
            finish(nil)
            return
        }
        let app = "share"
        let client = SquintClient()
        var out: Outcome?
        do {
            if provider.hasItemConformingToTypeIdentifier(UTType.image.identifier) {
                let (img, raw) = try await loadImage(provider)
                if let raw {
                    out = await client.check(fileData: raw, name: "shared.jpg", mime: "image/jpeg", app: app)
                } else {
                    out = await client.screenFlow(image: img, app: app, trigger: "share")
                }
            } else if provider.hasItemConformingToTypeIdentifier(UTType.movie.identifier) {
                let (data, name) = try await loadFile(provider, type: .movie)
                out = await client.check(fileData: data, name: name, mime: "video/mp4", app: app)
            } else if provider.hasItemConformingToTypeIdentifier(UTType.audio.identifier) {
                let (data, name) = try await loadFile(provider, type: .audio)
                out = await client.check(fileData: data, name: name, mime: "audio/mp4", app: app)
            } else if provider.hasItemConformingToTypeIdentifier(UTType.plainText.identifier) {
                let text = try await provider.loadItem(forTypeIdentifier: UTType.plainText.identifier) as? String ?? ""
                out = await client.check(text: text, app: app)
            } else if provider.hasItemConformingToTypeIdentifier(UTType.url.identifier) {
                let url = try await provider.loadItem(forTypeIdentifier: UTType.url.identifier) as? URL
                out = await client.check(text: "shared link: \(url?.absoluteString ?? "") \(item.attributedContentText?.string ?? "")", app: app)
            }
        } catch {
            out = nil
        }
        finish(out)
    }

    private func loadImage(_ p: NSItemProvider) async throws -> (UIImage, Data?) {
        let obj = try await p.loadItem(forTypeIdentifier: UTType.image.identifier)
        if let url = obj as? URL, let data = try? Data(contentsOf: url), let img = UIImage(data: data) { return (img, data) }
        if let data = obj as? Data, let img = UIImage(data: data) { return (img, data) }
        if let img = obj as? UIImage { return (img, nil) }
        throw SquintError.badImage
    }

    private func loadFile(_ p: NSItemProvider, type: UTType) async throws -> (Data, String) {
        let obj = try await p.loadItem(forTypeIdentifier: type.identifier)
        if let url = obj as? URL {
            return (try Data(contentsOf: url), url.lastPathComponent)
        }
        if let data = obj as? Data { return (data, "clip") }
        throw SquintError.badImage
    }

    private func finish(_ out: Outcome?) {
        DispatchQueue.main.async {
            if let out {
                Deliver.verdict(out)
                self.label.text = out.verdict.headline
            } else {
                Deliver.failed()
                self.label.text = "couldn't check that"
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.6) {
                self.extensionContext?.completeRequest(returningItems: nil)
            }
        }
    }
}
