A useful contract answers these questions:

- Who owns a key: an authenticated account, tenant, or another principal? Can a caller ever retrieve another principal's result?
- What identifies the operation? Reusing a key for a different request should produce a documented conflict instead of silently returning an unrelated success.
- Which request fields determine equivalence? Normalize deliberately; raw JSON serialization can differ without changing meaning. Hashing a canonical representation is one option, not a substitute for defining the contract.
- How long does the guarantee last, and what happens after expiry? Cleanup and retries must agree on that boundary.
- What response can be recovered, including status and relevant headers? Avoid retaining credentials or unnecessary personal data.

For work entirely inside one PostgreSQL database, a composite unique constraint can establish the operation's identity. Store the business change and its completed receipt in one transaction. A losing concurrent attempt must resolve the conflict and read the committed result before answering; account for PostgreSQL statement snapshots and transaction error handling when choosing the exact SQL sequence.

An alternative is a durable processing record with a claim and recovery policy. This can support longer work, but now crashes can leave incomplete records. Ownership, expiry, takeover, and prevention of stale completion become part of the design.

External delivery adds a separate boundary. Recording an outbox entry with the order can prevent a committed order from losing its delivery intent. A dispatcher can still deliver more than once, so the receiver needs deduplication or the business needs reconciliation. Do not claim that an outbox alone makes every external effect happen exactly once.

Monitor duplicates, conflicting payloads, wait time, incomplete work, retention growth, and recovery failures. Logs should help trace an operation without exposing another customer's request or response.
