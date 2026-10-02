import { onlineManager } from '@tanstack/react-query';

// Execute or fail now. In particular, never queue or retry the toggle endpoint.
export const listMutationOptions = {
  retry: false,
  networkMode: 'always',
} as const;

export function requireConnection() {
  if (!onlineManager.isOnline())
    throw new Error('You’re offline. Reconnect, then try again.');
}
