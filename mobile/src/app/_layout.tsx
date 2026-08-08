import { QueryClientProvider } from '@tanstack/react-query';
import { DarkTheme, DefaultTheme, Stack, ThemeProvider } from 'expo-router';
import { useColorScheme } from 'react-native';

import { AuthProvider } from '@/lib/auth-context';
import { queryClient } from '@/lib/query-client';

export default function RootLayout() {
  const colorScheme = useColorScheme();

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ThemeProvider value={colorScheme === 'dark' ? DarkTheme : DefaultTheme}>
          <Stack>
            <Stack.Screen name="index" options={{ title: 'Home' }} />
            <Stack.Screen name="login" options={{ title: 'Sign In', headerShown: false }} />
            <Stack.Screen name="lists/index" options={{ title: 'Lists' }} />
            <Stack.Screen name="lists/[id]" options={{ title: 'List' }} />
            <Stack.Screen name="learning/index" options={{ title: 'Learning' }} />
            <Stack.Screen name="learning/[id]" options={{ title: 'Note' }} />
            <Stack.Screen name="learning/review" options={{ title: 'Review' }} />
            <Stack.Screen name="wishlist/index" options={{ title: 'Wishlist' }} />
            <Stack.Screen name="wishlist/new" options={{ title: 'New Gift' }} />
            <Stack.Screen name="wishlist/[id]" options={{ title: 'Gift' }} />
            <Stack.Screen name="library/index" options={{ title: 'Library' }} />
            <Stack.Screen name="library/[id]" options={{ title: 'Playlist' }} />
            <Stack.Screen name="jobwizard/index" options={{ title: 'Jobwizard' }} />
            <Stack.Screen name="jobwizard/new" options={{ title: 'New Job' }} />
            <Stack.Screen name="jobwizard/[id]" options={{ title: 'Job' }} />
          </Stack>
        </ThemeProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}
