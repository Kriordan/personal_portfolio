import { focusManager, onlineManager } from '@tanstack/react-query';
import * as Network from 'expo-network';
import { useEffect } from 'react';
import { AppState, Platform } from 'react-native';

export function QueryLifecycle() {
  useEffect(() => {
    if (Platform.OS === 'web') return; // TanStack already handles browser focus/connectivity.
    focusManager.setFocused(AppState.currentState === 'active');
    const appState = AppState.addEventListener('change', (state) =>
      focusManager.setFocused(state === 'active'),
    );
    let active = true;
    let receivedEvent = false;
    const update = (state: Network.NetworkState) => {
      // Unknown reachability is not proof of being offline (e.g. a LAN development server).
      onlineManager.setOnline(
        state.isConnected !== false && state.isInternetReachable !== false,
      );
    };
    const network = Network.addNetworkStateListener((state) => {
      receivedEvent = true;
      update(state);
    });
    void Network.getNetworkStateAsync()
      .then((state) => {
        if (active && !receivedEvent) update(state);
      })
      .catch(() => {
        /* Keep attempting requests when native connectivity cannot be determined. */
      });
    return () => {
      active = false;
      appState.remove();
      network.remove();
      focusManager.setFocused(undefined);
    };
  }, []);
  return null;
}
