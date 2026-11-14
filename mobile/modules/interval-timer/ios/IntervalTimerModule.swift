import ExpoModulesCore

public class IntervalTimerModule: Module {
  private lazy var engine = IntervalAudioEngine { [weak self] snapshot in self?.sendEvent("onStatus", snapshot) }
  private let storageQueue = DispatchQueue(label: "portfolio.intervals.library")

  public func definition() -> ModuleDefinition {
    Name("IntervalTimer")
    Events("onStatus")

    AsyncFunction("prepare") { (json: String, promise: Promise) in
      self.engine.prepare(json) { result in
        switch result {
        case .success(let snapshot): promise.resolve(snapshot)
        case .failure(let error): promise.reject(error)
        }
      }
    }.runOnQueue(.main)
    AsyncFunction("play") { () throws -> [String: Any] in try self.engine.play(); return self.engine.snapshot() }.runOnQueue(.main)
    AsyncFunction("pause") { () -> [String: Any] in self.engine.pause(); return self.engine.snapshot() }.runOnQueue(.main)
    AsyncFunction("skip") { () throws -> [String: Any] in try self.engine.skip(); return self.engine.snapshot() }.runOnQueue(.main)
    AsyncFunction("stop") { () -> [String: Any] in self.engine.stop(); return self.engine.snapshot() }.runOnQueue(.main)
    AsyncFunction("snapshot") { () -> [String: Any] in self.engine.snapshot() }.runOnQueue(.main)
    AsyncFunction("setVolume") { (volume: Double) throws in try self.engine.setVolume(volume) }.runOnQueue(.main)
    AsyncFunction("preview") { (promise: Promise) in
      self.engine.preview { result in
        switch result {
        case .success: promise.resolve()
        case .failure(let error): promise.reject(error)
        }
      }
    }.runOnQueue(.main)

    AsyncFunction("readLibrary") { () throws -> String? in
      let url = try IntervalAudioEngine.directory(.applicationSupportDirectory).appendingPathComponent("workouts.json")
      guard FileManager.default.fileExists(atPath: url.path) else { return nil }
      return try String(contentsOf: url, encoding: .utf8)
    }.runOnQueue(storageQueue)
    AsyncFunction("writeLibrary") { (json: String) throws in
      guard let data = json.data(using: .utf8), data.count <= 8_000_000 else { throw IntervalError.invalidProgram }
      let url = try IntervalAudioEngine.directory(.applicationSupportDirectory).appendingPathComponent("workouts.json")
      try data.write(to: url, options: [.atomic, .completeFileProtectionUntilFirstUserAuthentication])
    }.runOnQueue(storageQueue)

    OnDestroy {
      DispatchQueue.main.async { self.engine.stop() }
    }
  }
}
