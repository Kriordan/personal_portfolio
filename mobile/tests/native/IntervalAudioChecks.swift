import Foundation
import AVFoundation

@main
enum IntervalAudioChecks {
  static func main() throws {
    let directory = FileManager.default.temporaryDirectory.appendingPathComponent("interval-check-" + UUID().uuidString)
    try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
    defer { try? FileManager.default.removeItem(at: directory) }

    let program = try IntervalProgram.decode("{\"name\":\"Check\",\"segments\":[{\"name\":\"Jog\",\"seconds\":5},{\"name\":\"Walk\",\"seconds\":4},{\"name\":\"Finish\",\"seconds\":1}]}")
    precondition(program.duration == 10)
    precondition(program.starts == [0, 5, 9])
    precondition(program.cues.map(\.at) == [0, 2, 5, 6, 9, 10])
    precondition(program.cues[1].text == "Walk in three seconds")
    let output = directory.appendingPathComponent("check.m4a")
    try IntervalComposer.render(program, clips: [:], output: output, cancellation: IntervalCancellation())
    let audio = try AVAudioFile(forReading: output)
    let duration = Double(audio.length) / audio.processingFormat.sampleRate
    precondition(abs(duration - 10.35) < 0.1, "Encoded audio has the wrong duration: \(duration)")
    let pcm = AVAudioPCMBuffer(pcmFormat: audio.processingFormat, frameCapacity: AVAudioFrameCount(audio.length))!
    try audio.read(into: pcm)
    let samples = pcm.floatChannelData![0]
    func power(_ time: Double) -> Float {
      let start = Int(time * audio.processingFormat.sampleRate)
      return (0..<500).map { abs(samples[start + $0]) }.reduce(0, +) / 500
    }
    for time in [0.02, 2.02, 5.02, 6.02, 9.02, 10.02] { precondition(power(time) > 0.03, "Missing cue at \(time)") }
    for time in [0.6, 1.5, 3, 4, 5.5, 7, 8, 9.5] { precondition(power(time) < 0.002, "Unexpected audio at \(time)") }

    let cancelled = IntervalCancellation(); cancelled.cancel()
    do {
      try IntervalComposer.render(program, clips: [:], output: directory.appendingPathComponent("cancelled.m4a"), cancellation: cancelled)
      preconditionFailure("Cancelled rendering succeeded")
    } catch IntervalError.cancelled {}

    let longProgram = try IntervalProgram.decode("{\"name\":\"34 minutes\",\"segments\":[{\"name\":\"Warm-up\",\"seconds\":300}," +
      Array(repeating: "{\"name\":\"Jog\",\"seconds\":120},{\"name\":\"Walk\",\"seconds\":60}", count: 8).joined(separator: ",") +
      ",{\"name\":\"Cool down\",\"seconds\":300}]}")
    let longOutput = directory.appendingPathComponent("full.m4a")
    try IntervalComposer.render(longProgram, clips: [:], output: longOutput, cancellation: IntervalCancellation())
    let full = try AVAudioFile(forReading: longOutput)
    precondition(abs(Double(full.length) / full.processingFormat.sampleRate - 2040.35) < 0.1)
    let bytes = try FileManager.default.attributesOfItem(atPath: longOutput.path)[.size] as! Int
    precondition(bytes < 20_000_000)
    // Exercise real system speech buffers and conversion, not just tone fallbacks.
    let speechJob = IntervalSpeechJob(program: program, directory: directory)
    var speechResult: Result<[String: URL], Error>?
    speechJob.start { speechResult = $0 }
    let deadline = Date().addingTimeInterval(60)
    while speechResult == nil && Date() < deadline { RunLoop.current.run(until: Date().addingTimeInterval(0.05)) }
    guard let speechResult else { speechJob.cancel(); throw IntervalError.speechUnavailable }
    let clips = try speechResult.get()
    precondition(clips.count == 3)
    let spoken = try IntervalComposer.readClip(clips["Jog"]!)
    precondition(!spoken.isEmpty && spoken.contains(where: { abs($0) > 0.01 }))
    let voicedOutput = directory.appendingPathComponent("spoken.m4a")
    try IntervalComposer.render(program, clips: clips, output: voicedOutput, cancellation: IntervalCancellation())
    let voiced = try AVAudioFile(forReading: voicedOutput)
    precondition(abs(Double(voiced.length) / voiced.processingFormat.sampleRate - duration) < 0.01)
    print("Native interval checks passed: cue positions, quiet gaps, cancellation, and 34-minute encoded duration (\(bytes) bytes).")
    print("System speech synthesis and PCM conversion passed; spoken cues do not change workout duration.")
  }
}
