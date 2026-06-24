import Foundation
import ImageIO
import Vision

struct OCRLine: Codable {
    let text: String
    let confidence: Float
    let x: Double
    let y: Double
    let width: Double
    let height: Double
}

struct OCRResult: Codable {
    let imageWidth: Int
    let imageHeight: Int
    let lines: [OCRLine]
}

guard CommandLine.arguments.count == 2 else {
    fputs("Usage: vision_ocr <image-path>\n", stderr)
    exit(2)
}

let imageURL = URL(fileURLWithPath: CommandLine.arguments[1])
guard
    let source = CGImageSourceCreateWithURL(imageURL as CFURL, nil),
    let image = CGImageSourceCreateImageAtIndex(source, 0, nil)
else {
    fputs("Could not load image\n", stderr)
    exit(1)
}

let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = true
request.recognitionLanguages = ["en-AU", "en-US"]

let handler = VNImageRequestHandler(cgImage: image)

do {
    try handler.perform([request])
} catch {
    fputs("Vision OCR failed: \(error)\n", stderr)
    exit(1)
}

let lines = (request.results ?? []).compactMap { observation -> OCRLine? in
    guard let candidate = observation.topCandidates(1).first else {
        return nil
    }

    let box = observation.boundingBox
    return OCRLine(
        text: candidate.string,
        confidence: candidate.confidence,
        x: box.origin.x,
        y: box.origin.y,
        width: box.width,
        height: box.height
    )
}

let result = OCRResult(
    imageWidth: image.width,
    imageHeight: image.height,
    lines: lines
)

do {
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.sortedKeys]
    let data = try encoder.encode(result)
    FileHandle.standardOutput.write(data)
    FileHandle.standardOutput.write(Data([0x0A]))
} catch {
    fputs("Could not encode OCR result: \(error)\n", stderr)
    exit(1)
}
