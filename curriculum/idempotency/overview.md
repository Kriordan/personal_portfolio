Idempotency lets a caller repeat an operation without repeating its intended effect. It is useful when the caller cannot tell whether an earlier attempt succeeded. A timeout says that a response was not received in time; it does not prove that the server rolled back.

Imagine a client submitting an order. The server commits the order, but the response is lost. A second request should recover the first result rather than create a second order. That promise needs a scope, a definition of the same operation, and a retention window.

HTTP method semantics and application deduplication are related but distinct. A POST endpoint can offer an idempotency-key contract even though POST is not inherently idempotent. An idempotent operation need not return an identical response on every attempt: the guarantee concerns its intended effect. Other observable events, such as request logs, may still occur for each attempt.

By the end of this lesson, explain what a timeout leaves uncertain, define the scope of an idempotency key, defend a concurrency-safe design, and identify where that design's guarantee ends.
