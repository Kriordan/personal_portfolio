import type { ConfigContext, ExpoConfig } from 'expo/config';

export default ({ config }: ConfigContext): ExpoConfig => {
  // Standalone previews and production builds must not silently target localhost.
  const profile = process.env.EAS_BUILD_PROFILE;
  if (profile === 'preview' || profile === 'production') {
    let apiUrl: URL;
    try {
      apiUrl = new URL(process.env.EXPO_PUBLIC_API_URL ?? '');
    } catch {
      throw new Error(
        `Set EXPO_PUBLIC_API_URL for the EAS ${profile} profile before building.`,
      );
    }
    if (
      apiUrl.protocol !== 'https:' ||
      ['localhost', '127.0.0.1', '10.0.2.2', '[::1]'].includes(apiUrl.hostname)
    ) {
      throw new Error(
        `${profile} EXPO_PUBLIC_API_URL must be an HTTPS API origin reachable by devices.`,
      );
    }
  }
  // EAS secrets are available to the worker, not necessarily to local config
  // resolution. Fail the enabled worker build if symbol upload is incomplete.
  if (process.env.EAS_BUILD === 'true' && process.env.EXPO_PUBLIC_SENTRY_ENABLED === '1') {
    const required = ['EXPO_PUBLIC_SENTRY_DSN', 'EXPO_PUBLIC_SENTRY_ENVIRONMENT',
      'SENTRY_ORG', 'SENTRY_PROJECT', 'SENTRY_AUTH_TOKEN'];
    if (required.some((name) => !process.env[name]?.trim())) {
      throw new Error('Enabled Sentry builds require a DSN, environment, organization, project and upload token.');
    }
  }
  const commit = process.env.EAS_BUILD_GIT_COMMIT_HASH;
  return {
    ...config,
    extra: {
      ...config.extra,
      ...(commit && /^[a-f0-9]{7,40}$/.test(commit) ? { monitoringCommit: commit } : {}),
    },
    plugins: [
      ...(config.plugins ?? []),
      ...(process.env.EXPO_PUBLIC_SENTRY_ENABLED === '1' ? [['@sentry/react-native/expo', {
        organization: process.env.SENTRY_ORG,
        project: process.env.SENTRY_PROJECT,
        // The upload token stays in the build environment, never app config.
      }]] : []),
    ],
  } as ExpoConfig;
};
