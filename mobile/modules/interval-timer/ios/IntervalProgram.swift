import Foundation
import AVFoundation

enum IntervalError: Error, LocalizedError {
  case invalidProgram, cancelled, speechUnavailable, renderFailed, busy
  var errorDescription: String? {
    switch self {
    case .invalidProgram: return "The workout is invalid or exceeds four hours / 500 intervals."
    case .cancelled: return "Audio preparation was cancelled."
    case .speechUnavailable: return "The iPhone could not prepare its spoken cues. Please try again."
    case .renderFailed: return "The workout audio could not be prepared or played."
    case .busy: return "End the current workout before starting another."
    }
  }
}

struct IntervalProgram: Decodable {
  struct Segment: Decodable { let name: String; let seconds: Int }
  let name: String
  let segments: [Segment]
  var duration: Double { Double(segments.reduce(0) { $0 + $1.seconds }) }
  var starts: [Double] {
    var cursor = 0.0
    return segments.map { segment in
      defer { cursor += Double(segment.seconds) }
      return cursor
    }
  }

  static func decode(_ json: String) throws -> IntervalProgram {
    guard let data = json.data(using: .utf8), data.count <= 250_000 else { throw IntervalError.invalidProgram }
    let program = try JSONDecoder().decode(IntervalProgram.self, from: data)
    guard !program.name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
          program.name.count <= 80, !program.segments.isEmpty, program.segments.count <= 500,
          program.segments.allSatisfy({ !$0.name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            && $0.name.count <= 80 && $0.seconds > 0 && $0.seconds <= 14_400 }),
          program.duration <= 14_400 else { throw IntervalError.invalidProgram }
    return program
  }

  struct Cue {
    let at: Double
    let text: String?
    let window: Double
    let frequency: Double
  }

  var cues: [Cue] {
    var result: [Cue] = []
    var cursor = 0.0
    for (index, segment) in segments.enumerated() {
      // Speech can never cross a later cue, even in a one-second workout.
      let firstWindow = min(3, Double(segment.seconds) - (segment.seconds > 3 ? 3 : 0))
      result.append(Cue(at: cursor, text: index == 0 ? segment.name : nil,
                        window: index == 0 ? firstWindow : 0.16, frequency: 880))
      cursor += Double(segment.seconds)
      if segment.seconds > 3 {
        let next = index + 1 < segments.count ? segments[index + 1].name : "Finish"
        result.append(Cue(at: cursor - 3, text: "\(next) in three seconds", window: 2.8, frequency: 660))
      }
    }
    // The finish tone has a short audio tail; workout duration remains exact.
    result.append(Cue(at: cursor, text: nil, window: 0.35, frequency: 1174))
    return result
  }
}

final class IntervalCancellation: @unchecked Sendable {
  private let lock = NSLock()
  private var stopped = false
  func cancel() { lock.lock(); stopped = true; lock.unlock() }
  func check() throws {
    lock.lock(); let cancelled = stopped; lock.unlock()
    if cancelled { throw IntervalError.cancelled }
  }
}

/** Chunked encoding keeps memory independent of the workout's duration. */
enum IntervalComposer {
  static let sampleRate = 24_000.0
  static let format = AVAudioFormat(standardFormatWithSampleRate: sampleRate, channels: 1)!

  static func readClip(_ url: URL) throws -> [Float] {
    let file = try AVAudioFile(forReading: url)
    // Overlong phrases become a warning tone, not truncated spoken words.
    guard Double(file.length) / file.processingFormat.sampleRate <= 3.05 else { return [] }
    guard file.length > 0,
          let source = AVAudioPCMBuffer(pcmFormat: file.processingFormat, frameCapacity: AVAudioFrameCount(file.length)),
          let converter = AVAudioConverter(from: file.processingFormat, to: format),
          let output = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: AVAudioFrameCount(sampleRate * 3.1)) else {
      throw IntervalError.renderFailed
    }
    try file.read(into: source)
    var fed = false
    var error: NSError?
    let status = converter.convert(to: output, error: &error) { _, state in
      if fed { state.pointee = .endOfStream; return nil }
      fed = true
      state.pointee = .haveData
      return source
    }
    if let error { throw error }
    guard status != .error, output.frameLength > 0, let data = output.floatChannelData?[0] else { throw IntervalError.renderFailed }
    return Array(UnsafeBufferPointer(start: data, count: Int(output.frameLength)))
  }

  static func tone(seconds: Double, frequency: Double) -> [Float] {
    let frames = Int(seconds * sampleRate)
    return (0..<frames).map { index in
      let envelope = min(1, Double(min(index, frames - 1 - index)) / (sampleRate * 0.012))
      return Float(sin(2 * .pi * frequency * Double(index) / sampleRate) * 0.35 * envelope)
    }
  }

  static func render(_ program: IntervalProgram, clips: [String: URL], output: URL,
                     cancellation: IntervalCancellation) throws {
    let file = try AVAudioFile(forWriting: output, settings: [
      AVFormatIDKey: kAudioFormatMPEG4AAC, AVSampleRateKey: sampleRate,
      AVNumberOfChannelsKey: 1, AVEncoderBitRateKey: 48_000,
    ], commonFormat: .pcmFormatFloat32, interleaved: false)
    let chunk = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: 4096)!
    var cursor: Int64 = 0
    func write(_ samples: [Float]?, count: Int64) throws {
      var offset: Int64 = 0
      while offset < count {
        try cancellation.check()
        let size = Int(min(4096, count - offset))
        chunk.frameLength = AVAudioFrameCount(size)
        let target = chunk.floatChannelData![0]
        if let samples {
          samples.withUnsafeBufferPointer { source in
            target.update(from: source.baseAddress! + Int(offset), count: size)
          }
        } else { target.update(repeating: 0, count: size) }
        try file.write(from: chunk)
        offset += Int64(size)
        cursor += Int64(size)
      }
    }
    for cue in program.cues {
      let start = Int64((cue.at * sampleRate).rounded())
      guard start >= cursor else { throw IntervalError.renderFailed }
      try write(nil, count: start - cursor)
      var samples: [Float] = []
      if let text = cue.text, let url = clips[text] { samples = try readClip(url) }
      if samples.isEmpty || Double(samples.count) / sampleRate > cue.window {
        samples = tone(seconds: min(cue.window, cue.text == nil ? cue.window : 0.12), frequency: cue.frequency)
      }
      try write(samples, count: Int64(samples.count))
    }
    try cancellation.check()
    // Closing by releasing AVAudioFile finalizes AAC before the caller opens it.
  }
}
