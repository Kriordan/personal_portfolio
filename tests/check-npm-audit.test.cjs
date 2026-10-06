const assert = require('node:assert/strict');
const { test } = require('node:test');
const { checkAudit } = require('../scripts/check-npm-audit.cjs');

const id = 'GHSA-test-test-test';
const exception = { id, package: 'example', version: '1.0.0', severity: 'high', reviewBy: '2026-11-05' };
const lock = { packages: { 'node_modules/example': { version: '1.0.0' } } };
function report() {
  return { auditReportVersion: 2, metadata: { vulnerabilities: { high: 1 } }, vulnerabilities: {
    example: { nodes: ['node_modules/example'], via: [{ url: `https://github.com/advisories/${id}`, severity: 'high' }] },
    parent: { via: ['example'] },
  } };
}
const check = (value, exceptions = [exception], today = '2026-10-05') => checkAudit(value, lock, exceptions, today);
test('accepts reviewed advisory and affected parent', () => assert.deepEqual(check(report()), [id]));
test('rejects a new advisory on an already excepted package', () => {
  const value = report();
  value.vulnerabilities.example.via[0].url = 'https://github.com/advisories/GHSA-new1-new2-new3';
  assert.throws(() => check(value), /Unreviewed/);
});
test('rejects failed or malformed audits', () => {
  assert.throws(() => check({ error: 'registry unavailable' }));
  assert.throws(() => check({ ...report(), error: 'registry unavailable' }));
});
test('rejects changed versions, severity, expired and stale exceptions', () => {
  assert.throws(() => check(report(), [{ ...exception, version: '2.0.0' }]), /version changed/);
  assert.throws(() => check(report(), [{ ...exception, severity: 'moderate' }]), /Severity changed/);
  assert.throws(() => check(report(), [exception], '2026-11-06'), /expired/);
  assert.throws(() => check({ ...report(), vulnerabilities: {} }), /stale/);
});
