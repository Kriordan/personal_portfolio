import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';

if (process.platform !== 'darwin') {
  console.error('Native interval audio checks require macOS and Xcode.');
  process.exit(1);
}
const scratch = mkdtempSync(join(tmpdir(), 'interval-audio-tests-'));
const binary = join(scratch, 'checks');
try {
  for (const [command, args] of [
    ['xcrun', ['swiftc', '-module-cache-path', join(scratch, 'cache'),
      resolve('modules/interval-timer/ios/IntervalProgram.swift'),
      resolve('modules/interval-timer/ios/IntervalSpeechJob.swift'),
      resolve('tests/native/IntervalAudioChecks.swift'), '-o', binary]],
    [binary, []],
  ]) {
    const result = spawnSync(command, args, { stdio: 'inherit', timeout: 180_000 });
    if (result.error) throw result.error;
    if (result.status !== 0) { process.exitCode = result.status ?? 1; break; }
  }
} finally { rmSync(scratch, { recursive: true, force: true }); }
