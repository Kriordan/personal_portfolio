import { useCallback, useRef, useState } from 'react';

/** The ref closes the gap before React re-renders a disabled submit control. */
export function useSubmission() {
  const locked = useRef(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async (action: () => Promise<unknown>) => {
    if (locked.current) return;
    locked.current = true;
    setPending(true);
    setError(null);
    try {
      await action();
    } catch (cause) {
      setError(
        cause instanceof Error && cause.name === 'ApiError'
          ? cause.message
          : 'Couldn’t confirm the request. Check your connection and try again.',
      );
    } finally {
      locked.current = false;
      setPending(false);
    }
  }, []);
  return { run, pending, error };
}
