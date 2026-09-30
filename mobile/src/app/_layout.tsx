import { QueryClientProvider } from '@tanstack/react-query';
import { DarkTheme, DefaultTheme, Stack, ThemeProvider } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useColorScheme } from 'react-native';

import { ScreenState } from '@/components/screen';
import { useTheme } from '@/hooks/use-theme';
import { AuthProvider, useAuth } from '@/lib/auth-context';
import { queryClient } from '@/lib/query-client';
import { QueryLifecycle } from '@/lib/query-lifecycle';

// Cold deep links open above the shell, preserving an ordinary Back destination.
export const unstable_settings = { anchor: '(tabs)' };

function AppNavigation() {
  const { isAuthenticated } = useAuth();
  const theme = useTheme();
  if (isAuthenticated === null)
    return <ScreenState loading title="Restoring your session" />;

  return (
    <Stack
      screenOptions={{
        headerTintColor: theme.accent,
        headerStyle: { backgroundColor: theme.background },
        headerTitleStyle: { color: theme.text },
        headerShadowVisible: false,
        headerBackButtonDisplayMode: 'minimal',
        contentStyle: { backgroundColor: theme.background },
      }}
    >
      <Stack.Protected guard={isAuthenticated}>
        <Stack.Screen
          name="(tabs)"
          options={{ headerShown: false, title: 'Home' }}
        />
        <Stack.Screen name="lists/index" options={{ title: 'Grocery' }} />
        <Stack.Screen name="lists/[id]" options={{ title: 'Grocery list' }} />
        <Stack.Screen name="learning/index" options={{ title: 'Learning' }} />
        <Stack.Screen name="learning/[id]" options={{ title: 'Note' }} />
        <Stack.Screen name="learning/review" options={{ title: 'Review' }} />
        <Stack.Screen name="wishlist/index" options={{ title: 'Wishlist' }} />
        <Stack.Screen name="wishlist/new" options={{ title: 'New gift' }} />
        <Stack.Screen name="wishlist/[id]" options={{ title: 'Gift' }} />
        <Stack.Screen name="library/index" options={{ title: 'Library' }} />
        <Stack.Screen name="library/[id]" options={{ title: 'Playlist' }} />
        <Stack.Screen name="jobwizard/index" options={{ title: 'Jobwizard' }} />
        <Stack.Screen name="jobwizard/new" options={{ title: 'New job' }} />
        <Stack.Screen name="jobwizard/[id]" options={{ title: 'Job' }} />
      </Stack.Protected>
      <Stack.Protected guard={!isAuthenticated}>
        <Stack.Screen name="login" options={{ headerShown: false }} />
      </Stack.Protected>
    </Stack>
  );
}

export default function RootLayout() {
  const colorScheme = useColorScheme();
  return (
    <QueryClientProvider client={queryClient}>
      <QueryLifecycle />
      <AuthProvider>
        <ThemeProvider
          value={colorScheme === 'dark' ? DarkTheme : DefaultTheme}
        >
          <StatusBar style={colorScheme === 'dark' ? 'light' : 'dark'} />
          <AppNavigation />
        </ThemeProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}
