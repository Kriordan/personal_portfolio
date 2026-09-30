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
  return config as ExpoConfig;
};
