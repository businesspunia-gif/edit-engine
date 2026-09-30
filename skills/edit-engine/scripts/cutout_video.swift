// Person cut-out with Apple Vision (macOS 14+). Writes raw BGRA frames at the
// source resolution to stdout; make_cutout.sh pipes them into ffmpeg.
// usage: cutout_video <in.mp4> [startSec] [durSec]
import Foundation
import AVFoundation
import Vision
import CoreImage

let a = CommandLine.arguments
guard a.count >= 2 else { fputs("usage: cutout_video in.mp4 [start] [dur]\n", stderr); exit(2) }
let start = a.count > 2 ? Double(a[2])! : 0
let dur = a.count > 3 ? Double(a[3])! : 0

let asset = AVURLAsset(url: URL(fileURLWithPath: a[1]))
let track = asset.tracks(withMediaType: .video).first!
let size = track.naturalSize.applying(track.preferredTransform)
let W = Int(abs(size.width)), Hh = Int(abs(size.height))
FileHandle.standardError.write("size \(W)x\(Hh)\n".data(using: .utf8)!)

let reader = try AVAssetReader(asset: asset)
if dur > 0 {
    reader.timeRange = CMTimeRange(start: CMTime(seconds: start, preferredTimescale: 600),
                                   duration: CMTime(seconds: dur, preferredTimescale: 600))
}
let out = AVAssetReaderTrackOutput(track: track, outputSettings: [
    kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA])
out.alwaysCopiesSampleData = false
reader.add(out)
reader.startReading()

let ctx = CIContext(options: [.useSoftwareRenderer: false])
let req = VNGeneratePersonSegmentationRequest()
req.qualityLevel = .accurate
req.outputPixelFormat = kCVPixelFormatType_OneComponent8

// Person segmentation does not count held or worn objects as "person": a mic in
// front of the chest comes out as a mic-shaped hole through the torso. The
// foreground-instance mask (subject lift) includes it but has coarser hair
// edges, and the hair edge is the whole point. So: union of both, with the
// foreground mask eroded first so it can never add a halo outside the real
// silhouette. The mic is a large solid region and survives the erosion.
let fgReq: VNGenerateForegroundInstanceMaskRequest? = {
    if #available(macOS 14.0, *) { return VNGenerateForegroundInstanceMaskRequest() }
    return nil
}()
let FG_ERODE: Double = 8

let stdout = FileHandle.standardOutput
var prev: CIImage? = nil          // temporal smoothing to kill mask flicker
var n = 0
// Reused output buffers. Allocating per frame, and feeding an unmaterialised
// CIImage back in as `prev`, built an unbounded lazy filter graph: throughput
// fell from ~75 to ~7 frames/min over a 30s clip. Materialise every frame.
var pool: CVPixelBuffer? = nil
var maskPool: CVPixelBuffer? = nil
CVPixelBufferCreate(nil, W, Hh, kCVPixelFormatType_32BGRA, nil, &pool)
CVPixelBufferCreate(nil, W, Hh, kCVPixelFormatType_OneComponent8, nil, &maskPool)

while let sb = out.copyNextSampleBuffer() {
    guard let pb = CMSampleBufferGetImageBuffer(sb) else { continue }
    var img = CIImage(cvPixelBuffer: pb)
    // apply track orientation
    img = img.transformed(by: track.preferredTransform).transformed(
        by: CGAffineTransform(translationX: -img.transformed(by: track.preferredTransform).extent.origin.x,
                              y: -img.transformed(by: track.preferredTransform).extent.origin.y))

    let handler = VNImageRequestHandler(ciImage: img, options: [:])
    try handler.perform([req])
    guard let obs = req.results?.first else { continue }

    var mask = CIImage(cvPixelBuffer: obs.pixelBuffer)
    mask = mask.transformed(by: CGAffineTransform(scaleX: img.extent.width / mask.extent.width,
                                                  y: img.extent.height / mask.extent.height))
    mask = mask.applyingGaussianBlur(sigma: 1.4).cropped(to: img.extent)

    if #available(macOS 14.0, *), let fr = fgReq {
        let h = VNImageRequestHandler(ciImage: img, options: [:])
        if (try? h.perform([fr])) != nil, let fo = fr.results?.first,
           let fbuf = try? fo.generateScaledMaskForImage(forInstances: fo.allInstances, from: h) {
            var fg = CIImage(cvPixelBuffer: fbuf)
            fg = fg.transformed(by: CGAffineTransform(scaleX: img.extent.width / fg.extent.width,
                                                     y: img.extent.height / fg.extent.height))
            fg = fg.applyingFilter("CIMorphologyMinimum", parameters: [kCIInputRadiusKey: FG_ERODE])
                   .cropped(to: img.extent)
            mask = mask.applyingFilter("CIMaximumCompositing",
                                       parameters: [kCIInputBackgroundImageKey: fg])
                       .cropped(to: img.extent)
        }
    }
    if let p = prev {
        mask = mask.applyingFilter("CIDissolveTransition",
                                   parameters: [kCIInputTargetImageKey: p, kCIInputTimeKey: 0.35])
                   .cropped(to: img.extent)
    }
    if let mp = maskPool {
        ctx.render(mask, to: mp, bounds: img.extent, colorSpace: nil)
        prev = CIImage(cvPixelBuffer: mp).cropped(to: img.extent)
    } else {
        prev = mask
    }

    let masked = img.applyingFilter("CIBlendWithMask", parameters: [
        kCIInputBackgroundImageKey: CIImage(color: .clear).cropped(to: img.extent),
        kCIInputMaskImageKey: mask])

    guard let b = pool else { continue }
    ctx.render(masked, to: b, bounds: img.extent, colorSpace: CGColorSpaceCreateDeviceRGB())
    CVPixelBufferLockBaseAddress(b, .readOnly)
    let bpr = CVPixelBufferGetBytesPerRow(b)
    let base = CVPixelBufferGetBaseAddress(b)!
    for row in 0..<Hh {
        stdout.write(Data(bytes: base.advanced(by: row * bpr), count: W * 4))
    }
    CVPixelBufferUnlockBaseAddress(b, .readOnly)
    n += 1
    if n % 30 == 0 { FileHandle.standardError.write("\(n)\n".data(using: .utf8)!) }
}
FileHandle.standardError.write("frames \(n) status \(reader.status.rawValue) \(reader.error?.localizedDescription ?? "-")\n".data(using: .utf8)!)
