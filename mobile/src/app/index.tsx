import { Redirect, useRouter } from 'expo-router';
import { ActivityIndicator, Pressable, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { MaxContentWidth, Spacing } from '@/constants/theme';
import { API_BASE_URL } from '@/lib/config';
import { useAuth } from '@/lib/auth-context';

export default function HomeScreen() {
  const { isAuthenticated, user, signOut } = useAuth();
  const router = useRouter();

  if (isAuthenticated === null) {
    return (
      <ThemedView style={styles.loading}>
        <ActivityIndicator />
      </ThemedView>
    );
  }

  if (!isAuthenticated) {
    return <Redirect href="/login" />;
  }

  return (
    <ThemedView style={styles.container}>
      <SafeAreaView style={styles.safeArea}>
        <ThemedText type="subtitle">Signed in</ThemedText>
        {user && <ThemedText>Welcome, {user.username}</ThemedText>}
        <ThemedText type="small" themeColor="textSecondary">
          API: {API_BASE_URL}
        </ThemedText>

        <Pressable style={styles.button} onPress={() => router.push('/lists')}>
          <ThemedText type="smallBold" style={styles.buttonText}>
            My Lists
          </ThemedText>
        </Pressable>

        <Pressable style={styles.buttonLearning} onPress={() => router.push('/learning')}>
          <ThemedText type="smallBold" style={styles.buttonText}>
            Learning
          </ThemedText>
        </Pressable>

        <Pressable style={styles.buttonLearning} onPress={() => router.push('/wishlist')}>
          <ThemedText type="smallBold" style={styles.buttonText}>
            Wishlist
          </ThemedText>
        </Pressable>

        <Pressable style={styles.buttonSecondary} onPress={signOut}>
          <ThemedText type="smallBold">Sign Out</ThemedText>
        </Pressable>
      </SafeAreaView>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  loading: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  container: {
    flex: 1,
    flexDirection: 'row',
    justifyContent: 'center',
  },
  safeArea: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    gap: Spacing.three,
    paddingHorizontal: Spacing.four,
    maxWidth: MaxContentWidth,
  },
  button: {
    backgroundColor: '#3c87f7',
    borderRadius: Spacing.two,
    paddingVertical: Spacing.three,
    paddingHorizontal: Spacing.five,
    alignItems: 'center',
    marginTop: Spacing.four,
  },
  buttonLearning: {
    backgroundColor: '#3c87f7',
    borderRadius: Spacing.two,
    paddingVertical: Spacing.three,
    paddingHorizontal: Spacing.five,
    alignItems: 'center',
  },
  buttonSecondary: {
    borderRadius: Spacing.two,
    paddingVertical: Spacing.three,
    paddingHorizontal: Spacing.five,
    alignItems: 'center',
  },
  buttonText: {
    color: '#ffffff',
  },
});
