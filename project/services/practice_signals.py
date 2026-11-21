"""A process-local wake-up for the Learning reply worker.

Set after a transaction that queued a reply commits. Missing a wake-up only delays that
reply until the worker's next poll, and another process's worker polls for itself.
"""
import threading

reply_queued = threading.Event()
