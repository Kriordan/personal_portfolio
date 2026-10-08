export class RequestTimeoutError extends Error {
  constructor() {
    super('The request timed out. The server may still be working.');
    this.name = 'RequestTimeoutError';
  }
}

/** Bound the entire request, including auth refresh and response body reading. */
export async function withRequestTimeout<T>(
  run: (signal?: AbortSignal) => Promise<T>,
  timeoutMs?: number,
): Promise<T> {
  if (timeoutMs === undefined) return run();
  const controller = new AbortController();
  let timer: ReturnType<typeof setTimeout>;
  const timeout = new Promise<never>((_resolve, reject) => {
    timer = setTimeout(() => {
      reject(new RequestTimeoutError());
      controller.abort();
    }, timeoutMs);
  });
  try {
    return await Promise.race([run(controller.signal), timeout]);
  } finally {
    clearTimeout(timer!);
  }
}
