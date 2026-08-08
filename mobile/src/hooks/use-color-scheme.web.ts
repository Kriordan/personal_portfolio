import { useSyncExternalStore } from 'react';
import { useColorScheme as useRNColorScheme } from 'react-native';

const emptySubscribe = () => () => {};

/**
 * To support static rendering, this value needs to be re-calculated on the
 * client side for web. Server snapshot is always 'light'; the client swaps in
 * the real scheme after hydration without a cascading effect render.
 */
export function useColorScheme() {
  const colorScheme = useRNColorScheme();
  return useSyncExternalStore(
    emptySubscribe,
    () => colorScheme,
    () => 'light' as const,
  );
}
