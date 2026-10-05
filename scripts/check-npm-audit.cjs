// Accept only individually reviewed advisory/package/version combinations.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

function checkAudit(report, lock, exceptions, today = new Date().toISOString().slice(0, 10)) {
  assert.equal(report.auditReportVersion, 2, 'Unsupported or failed npm audit response');
  assert.ok(!report.error && report.vulnerabilities && report.metadata?.vulnerabilities,
    'npm audit failed; cannot treat unavailable data as a clean scan');
  const seen = new Set();
  for (const [name, finding] of Object.entries(report.vulnerabilities)) {
    assert.ok(Array.isArray(finding.via) && finding.via.length, `Missing advisory data: ${name}`);
    for (const advisory of finding.via) {
      if (typeof advisory === 'string') {
        assert.ok(report.vulnerabilities[advisory], `Missing parent advisory: ${advisory}`);
        continue; // npm duplicates underlying findings on affected parents.
      }
      const id = advisory.url?.match(/\/advisories\/(GHSA-[\w-]+)$/)?.[1];
      const exception = exceptions.find(item => item.id === id && item.package === name);
      assert.ok(exception, `Unreviewed ${advisory.severity} advisory: ${name} ${id || advisory.url}`);
      assert.ok(exception.reviewBy >= today, `Re-review expired exception: ${id}`);
      assert.equal(advisory.severity, exception.severity, `Severity changed: ${id}`);
      assert.ok(finding.nodes.length, `Missing dependency locations: ${name}`);
      for (const node of finding.nodes) {
        assert.equal(lock.packages[node]?.version, exception.version, `Exception version changed: ${node}`);
      }
      seen.add(id);
    }
  }
  for (const exception of exceptions) {
    assert.ok(seen.has(exception.id), `Remove stale exception: ${exception.id}`);
  }
  return [...seen];
}

if (require.main === module) {
  const project = process.argv[2] || '.';
  assert.ok(['.', 'mobile'].includes(project), 'Expected . or mobile');
  const root = path.resolve(__dirname, '..');
  const cwd = path.join(root, project);
  const result = spawnSync('npm', ['audit', '--json'], {
    cwd, encoding: 'utf8', timeout: 120_000, maxBuffer: 10 * 1024 * 1024,
  });
  if (result.error) throw result.error;
  assert.ok(result.status === 0 || result.status === 1, result.stderr || 'npm audit failed');
  const lock = JSON.parse(fs.readFileSync(path.join(cwd, 'package-lock.json'), 'utf8'));
  const exceptions = require('../docs/security/npm-audit-exceptions.json')[project];
  const known = checkAudit(JSON.parse(result.stdout), lock, exceptions);
  console.log(`PASS: ${project}: no unreviewed advisories; ${known.length} documented exceptions`);
  for (const id of known) console.log(`OPEN: ${id}`);
}

module.exports = { checkAudit };
