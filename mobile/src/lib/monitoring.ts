import * as Sentry from '@sentry/react-native';
import Constants from 'expo-constants';
import { Platform } from 'react-native';
import { failureTags, scrubMobileEvent, type OperationFailure } from './monitoring-policy';

let active = false;
const reported = new Set<string>();

export function initializeMonitoring() {
  const dsn = process.env.EXPO_PUBLIC_SENTRY_DSN;
  if (active || __DEV__ || Platform.OS === 'web' ||
      process.env.EXPO_PUBLIC_SENTRY_ENABLED !== '1' || !dsn) return;
  try {
    Sentry.init({
      dsn,
      environment: process.env.EXPO_PUBLIC_SENTRY_ENVIRONMENT ?? 'preview',
      sendDefaultPii: false,
      // Expo 57's supported SDK cannot apply our JS scrubber to native crashes.
      // Keep those off until a separate native privacy/symbolication check.
      enableNativeCrashHandling: false,
      enableLogs: false,
      enableMetrics: false,
      enableAutoSessionTracking: false,
      enableWatchdogTerminationTracking: false,
      enableAppHangTracking: false,
      enableAutoPerformanceTracing: false,
      enableAppStartTracking: false,
      enableNativeFramesTracking: false,
      enableStallTracking: false,
      enableUserInteractionTracing: false,
      enableCaptureFailedRequests: false,
      attachScreenshot: false,
      attachViewHierarchy: false,
      attachThreads: false,
      maxBreadcrumbs: 0,
      beforeBreadcrumb: () => null,
      beforeSend: scrubMobileEvent,
      // Omit trace/profile/replay rates: even a zero rate installs integrations.
      integrations: (defaults) => defaults.filter((integration) =>
        !['Breadcrumbs', 'HttpContext', 'ExpoConstants', 'ExpoContext', 'ModulesLoader'].includes(integration.name)),
    });
    Sentry.setUser({ ip_address: '0.0.0.0' });
    const commit = Constants.expoConfig?.extra?.monitoringCommit;
    if (typeof commit === 'string' && /^[a-f0-9]{7,40}$/.test(commit))
      Sentry.setTag('commit', commit);
    active = true;
  } catch {
    // Monitoring must not prevent application startup.
  }
}

export function reportOperationFailure(failure: OperationFailure) {
  if (!active) return;
  const tags = failureTags(failure);
  if (!tags) return;
  const key = `${tags.request_id}:${tags.phase}:${tags.code}:${tags.status}`;
  if (reported.has(key)) return;
  if (reported.size >= 200) reported.delete(reported.values().next().value!);
  reported.add(key);
  try {
    Sentry.captureMessage('Jobwizard extraction request failed', { level: 'error', tags });
  } catch {
    // A reporting failure never changes the request outcome or triggers a retry.
  }
}
