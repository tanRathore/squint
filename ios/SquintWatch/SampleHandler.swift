import ReplayKit
import UIKit

final class SampleHandler: RPBroadcastSampleHandler {
    private var lastSent = Date.distantPast
    private let every: TimeInterval = 8
    private var inflight = false
    private let ctx = CIContext()

    override func processSampleBuffer(_ sampleBuffer: CMSampleBuffer, with sampleBufferType: RPSampleBufferType) {
        guard sampleBufferType == .video, !inflight, Date().timeIntervalSince(lastSent) > every else { return }
        guard let px = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        lastSent = Date()
        inflight = true
        let ci = CIImage(cvPixelBuffer: px)
        let scale = 720 / max(ci.extent.width, ci.extent.height)
        let small = ci.transformed(by: CGAffineTransform(scaleX: scale, y: scale))
        guard let cg = ctx.createCGImage(small, from: small.extent) else { inflight = false; return }
        let ui = UIImage(cgImage: cg)
        Task { [weak self] in
            defer { self?.inflight = false }
            _ = await SquintClient().watch(image: ui)
        }
    }

    override func broadcastFinished() {}
}
