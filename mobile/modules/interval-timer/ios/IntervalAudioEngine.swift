import Foundation
import AVFoundation
import CryptoKit
import UIKit

final class IntervalAudioEngine: NSObject, AVAudioPlayerDelegate {
  private var player: AVAudioPlayer?
  private var program: IntervalProgram?
  private var job: IntervalSpeechJob?
  private var generation = 0
  private var timer: Timer?
  private var observers: [NSObjectProtocol] = []
  private var state = "idle"
  private var reason: String?
  private var volume: Float = 1
  private var previewing = false
  private var previewCompletion: ((Result<Void, Error>) -> Void)?
  private let onChange: ([String: Any]) -> Void

  init(onChange: @escaping ([String: Any]) -> Void) {
    self.onChange = onChange
    super.init()
    // A force-quit can leave an unfinished speech job. No job exists at init.
    if let cache = try? Self.directory(.cachesDirectory),
       let files = try? FileManager.default.contentsOfDirectory(at: cache, includingPropertiesForKeys: [.isDirectoryKey]) {
      for file in files where (try? file.resourceValues(forKeys: [.isDirectoryKey]).isDirectory) == true {
        try? FileManager.default.removeItem(at: file)
      }
    }
    let center = NotificationCenter.default
    observers.append(center.addObserver(forName: AVAudioSession.interruptionNotification, object: nil, queue: .main) { [weak self] note in
      if let raw = note.userInfo?[AVAudioSessionInterruptionTypeKey] as? UInt,
         AVAudioSession.InterruptionType(rawValue: raw) == .began { self?.pause(reason: "Audio interrupted. Resume when you’re ready.") }
    })
    observers.append(center.addObserver(forName: AVAudioSession.routeChangeNotification, object: nil, queue: .main) { [weak self] note in
      if let raw = note.userInfo?[AVAudioSessionRouteChangeReasonKey] as? UInt,
         AVAudioSession.RouteChangeReason(rawValue: raw) == .oldDeviceUnavailable { self?.pause(reason: "Headphones disconnected. Resume when you’re ready.") }
    })
    observers.append(center.addObserver(forName: AVAudioSession.mediaServicesWereResetNotification, object: nil, queue: .main) { [weak self] _ in
      self?.stop(); self?.state = "error"; self?.reason = "Audio was reset. Start the workout again."; self?.emit()
    })
    observers.append(center.addObserver(forName: UIApplication.didEnterBackgroundNotification, object: nil, queue: .main) { [weak self] _ in
      guard let self else { return }
      self.timer?.invalidate(); self.timer = nil
      // Never start a newly prepared workout unexpectedly after leaving the app.
      if self.state == "preparing" { self.stop(); self.state = "error"; self.reason = "Preparation interrupted. Try again."; self.emit() }
    })
    observers.append(center.addObserver(forName: UIApplication.didBecomeActiveNotification, object: nil, queue: .main) { [weak self] _ in
      self?.observeProgress(); self?.emit()
    })
  }

  deinit { observers.forEach(NotificationCenter.default.removeObserver); timer?.invalidate() }

  static func directory(_ kind: FileManager.SearchPathDirectory) throws -> URL {
    let url = FileManager.default.urls(for: kind, in: .userDomainMask)[0].appendingPathComponent("Intervals", isDirectory: true)
    try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true,
      attributes: [.protectionKey: FileProtectionType.completeUntilFirstUserAuthentication])
    return url
  }

  func snapshot() -> [String: Any] {
    let duration = program?.duration ?? 0
    let position = min(duration, player?.currentTime ?? 0)
    if state == "running" && position >= duration { state = "completed"; reason = nil }
    return ["state": state, "position": position, "duration": duration, "reason": reason as Any? ?? NSNull()]
  }

  func emit() { if !previewing { onChange(snapshot()) } }

  private func observeProgress() {
    timer?.invalidate(); timer = nil
    guard state == "running", UIApplication.shared.applicationState == .active else { return }
    // Display-only polling. Cues are already encoded at their exact audio positions.
    timer = Timer.scheduledTimer(withTimeInterval: 0.25, repeats: true) { [weak self] _ in self?.emit() }
  }

  func prepare(_ json: String, preview: Bool = false, completion: @escaping (Result<[String: Any], Error>) -> Void) {
    guard !["preparing", "ready", "running", "paused"].contains(state) else { completion(.failure(IntervalError.busy)); return }
    stop()
    previewing = preview
    let owner = generation
    do {
      let next = try IntervalProgram.decode(json)
      program = next
      state = "preparing"; emit()
      let cache = try Self.directory(.cachesDirectory)
      let hash = SHA256.hash(data: Data(("interval-audio-v1:" + json).utf8)).map { String(format: "%02x", $0) }.joined()
      let target = cache.appendingPathComponent(preview ? "preview.m4a" : hash + ".m4a")
      if FileManager.default.fileExists(atPath: target.path) {
        do { try load(target); completion(.success(snapshot())); return }
        catch { try? FileManager.default.removeItem(at: target) }
      }
      let work = cache.appendingPathComponent(UUID().uuidString, isDirectory: true)
      try FileManager.default.createDirectory(at: work, withIntermediateDirectories: true)
      let speech = IntervalSpeechJob(program: next, directory: work)
      job = speech
      speech.start { [weak self, weak speech] result in
        guard let self, let speech else { completion(.failure(IntervalError.cancelled)); return }
        if owner != self.generation {
          try? FileManager.default.removeItem(at: work)
          completion(.failure(IntervalError.cancelled)); return
        }
        switch result {
        case .failure(let error):
          self.job = nil; self.state = "error"; self.reason = error.localizedDescription; self.emit()
          try? FileManager.default.removeItem(at: work)
          completion(.failure(error))
        case .success(let clips):
          let temporary = work.appendingPathComponent("workout.m4a")
          DispatchQueue.global(qos: .userInitiated).async {
            let render = Result { try IntervalComposer.render(next, clips: clips, output: temporary, cancellation: speech.cancellation) }
            DispatchQueue.main.async {
              defer { try? FileManager.default.removeItem(at: work) }
              guard owner == self.generation else { completion(.failure(IntervalError.cancelled)); return }
              self.job = nil
              do {
                try render.get()
                try FileManager.default.moveItem(at: temporary, to: target)
                try self.load(target)
                // Keep just the latest successful render. Scratch directories belong to jobs.
                if !preview {
                  for old in try FileManager.default.contentsOfDirectory(at: cache, includingPropertiesForKeys: nil)
                    where old.pathExtension == "m4a" && old != target && old.lastPathComponent != "preview.m4a" {
                      try? FileManager.default.removeItem(at: old)
                    }
                }
                completion(.success(self.snapshot()))
              } catch {
                self.state = "error"; self.reason = error.localizedDescription; self.emit()
                completion(.failure(error))
              }
            }
          }
        }
      }
    } catch {
      state = "error"; reason = error.localizedDescription; emit(); completion(.failure(error))
    }
  }

  private func load(_ url: URL) throws {
    let audio = try AVAudioPlayer(contentsOf: url)
    guard let program, abs(audio.duration - program.duration - 0.35) < 0.25, audio.prepareToPlay() else { throw IntervalError.renderFailed }
    audio.volume = volume; audio.delegate = self
    player = audio; state = "ready"; reason = nil; emit()
  }

  func play() throws {
    guard ["ready", "paused"].contains(state), let player else { throw IntervalError.renderFailed }
    let session = AVAudioSession.sharedInstance()
    do {
      try session.setCategory(.playback, mode: .default, options: [.mixWithOthers])
      try session.setActive(true)
      guard player.play() else { throw IntervalError.renderFailed }
      state = "running"; reason = nil; observeProgress(); emit()
    } catch {
      state = "error"; reason = error.localizedDescription; deactivate(); emit(); throw error
    }
  }

  func pause(reason: String? = nil) {
    guard state == "running" else { return }
    if previewing { stop(); return }
    player?.pause(); state = "paused"; self.reason = reason
    timer?.invalidate(); timer = nil
    deactivate(); emit()
  }

  func skip() throws {
    guard ["running", "paused"].contains(state), let player, let program else { throw IntervalError.renderFailed }
    let position = player.currentTime
    let next = program.starts.first(where: { $0 > position + 0.01 }) ?? program.duration
    player.currentTime = next
    if next >= program.duration {
      state = "completed"; reason = nil
      // A paused skip finishes quietly; a running skip plays the finish tone.
      if !player.isPlaying { deactivate() }
    }
    emit()
  }

  func setVolume(_ value: Double) throws {
    guard value.isFinite, value >= 0.1, value <= 1 else { throw IntervalError.invalidProgram }
    volume = Float(value); player?.volume = volume
  }

  func preview(completion: @escaping (Result<Void, Error>) -> Void) {
    guard ["idle", "completed", "error"].contains(state) else { completion(.failure(IntervalError.busy)); return }
    let json = "{\"name\":\"Sound preview\",\"segments\":[{\"name\":\"Jog in three seconds\",\"seconds\":3}]}"
    prepare(json, preview: true) { [weak self] result in
      guard let self else { completion(.failure(IntervalError.cancelled)); return }
      do { _ = try result.get(); try self.play(); self.previewCompletion = completion }
      catch { self.previewing = false; completion(.failure(error)) }
    }
  }

  func stop() {
    generation += 1
    let oldJob = job; job = nil
    oldJob?.cancel()
    player?.stop(); player = nil; program = nil
    timer?.invalidate(); timer = nil
    state = "idle"; reason = nil; previewing = false
    let previewCallback = previewCompletion; previewCompletion = nil
    previewCallback?(.failure(IntervalError.cancelled))
    deactivate(); emit()
  }

  private func deactivate() { try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation) }

  func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) {
    guard player === self.player else { return }
    timer?.invalidate(); timer = nil
    if previewing {
      let callback = previewCompletion; previewCompletion = nil
      stop(); callback?(flag ? .success(()) : .failure(IntervalError.renderFailed)); return
    }
    state = flag ? "completed" : "error"
    reason = flag ? nil : "Audio playback stopped. Start the workout again."
    // AVAudioPlayer resets its time at EOF; pin it for the completed snapshot.
    player.currentTime = program?.duration ?? 0
    deactivate(); emit()
  }

  func audioPlayerDecodeErrorDidOccur(_ player: AVAudioPlayer, error: Error?) {
    guard player === self.player else { return }
    if previewing { stop(); return }
    state = "error"; reason = "Audio playback stopped. Start the workout again."
    timer?.invalidate(); timer = nil; deactivate(); emit()
  }
}
