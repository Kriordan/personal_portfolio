import Foundation
import AVFoundation

/** All mutable speech-job state is confined to the main queue. */
final class IntervalSpeechJob {
  let cancellation = IntervalCancellation()
  private let synthesizer = AVSpeechSynthesizer()
  private let directory: URL
  private var pending: [String]
  private var clips: [String: URL] = [:]
  private var output: AVAudioFile?
  private var timeout: DispatchWorkItem?
  private var completion: ((Result<[String: URL], Error>) -> Void)?
  private var utteranceID = UUID()

  init(program: IntervalProgram, directory: URL) {
    self.directory = directory
    pending = Array(Set(program.cues.compactMap(\.text))).sorted()
    #if os(iOS)
    synthesizer.usesApplicationAudioSession = false
    #endif
  }

  func start(_ completion: @escaping (Result<[String: URL], Error>) -> Void) {
    self.completion = completion
    next()
  }

  func cancel() {
    cancellation.cancel()
    finish(.failure(IntervalError.cancelled))
    synthesizer.stopSpeaking(at: .immediate)
  }

  private func finish(_ result: Result<[String: URL], Error>) {
    timeout?.cancel(); timeout = nil
    output = nil
    let callback = completion
    completion = nil
    callback?(result)
  }

  private func next() {
    guard completion != nil else { return }
    guard let text = pending.first else { finish(.success(clips)); return }
    pending.removeFirst()
    let id = UUID()
    utteranceID = id
    let url = directory.appendingPathComponent("\(id).caf")
    let utterance = AVSpeechUtterance(string: text)
    guard let voice = AVSpeechSynthesisVoice(language: "en-US") else {
      finish(.failure(IntervalError.speechUnavailable)); return
    }
    utterance.voice = voice
    utterance.rate = AVSpeechUtteranceDefaultSpeechRate
    let deadline = DispatchWorkItem { [weak self] in
      guard let self, self.utteranceID == id, self.completion != nil else { return }
      self.finish(.failure(IntervalError.speechUnavailable))
      self.synthesizer.stopSpeaking(at: .immediate)
    }
    timeout = deadline
    DispatchQueue.main.asyncAfter(deadline: .now() + 20, execute: deadline)
    synthesizer.write(utterance) { [weak self] buffer in
      guard let pcm = buffer as? AVAudioPCMBuffer else { return }
      // AVSpeech owns its callback buffers; copy before dispatching off its queue.
      let copy = AVAudioPCMBuffer(pcmFormat: pcm.format, frameCapacity: max(1, pcm.frameLength))!
      copy.frameLength = pcm.frameLength
      let source = UnsafeMutableAudioBufferListPointer(pcm.mutableAudioBufferList)
      let target = UnsafeMutableAudioBufferListPointer(copy.mutableAudioBufferList)
      for index in source.indices {
        if let from = source[index].mData, let to = target[index].mData {
          memcpy(to, from, Int(source[index].mDataByteSize))
        }
      }
      DispatchQueue.main.async {
        guard let self, self.completion != nil, self.utteranceID == id else { return }
        do {
          try self.cancellation.check()
          if copy.frameLength == 0 {
            self.timeout?.cancel()
            guard let file = self.output, file.length > 0 else { throw IntervalError.speechUnavailable }
            self.output = nil
            self.clips[text] = url
            self.next()
          } else {
            if self.output == nil { self.output = try AVAudioFile(forWriting: url, settings: copy.format.settings) }
            // Only retain enough audio to detect overflow of a three-second cue.
            if let output = self.output, Double(output.length) / output.processingFormat.sampleRate < 3.1 {
              try output.write(from: copy)
            }
          }
        } catch {
          self.finish(.failure(error))
          self.synthesizer.stopSpeaking(at: .immediate)
        }
      }
    }
  }
}
