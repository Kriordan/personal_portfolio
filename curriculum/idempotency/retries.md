Consider this sequence:

1. The client creates key `order-123` for one logical order and sends its request.
2. The server creates an order and commits the database transaction.
3. The response is lost. The client sees a timeout.
4. The client retries the same operation with the same key and equivalent payload.
5. The server recognizes the committed operation and returns its recorded result.

Now move the crash to before commit. The transaction should leave no committed order or successful receipt, and a later attempt can do the work. Move it to after commit but before the reply: the recorded result must still be recoverable.

Two simultaneous attempts are harder than two sequential attempts. Both can observe an absent receipt before either inserts it. A prior lookup alone is not a concurrency boundary. The design needs a database-enforced conflict point, a transaction, and a documented behavior for a competing request while the first is unresolved.

A timeout from a downstream system creates another uncertainty. Retrying a payment or warehouse action is safe only if that system participates in an appropriate deduplication or reconciliation protocol. A local transaction cannot roll back a remote side effect.
