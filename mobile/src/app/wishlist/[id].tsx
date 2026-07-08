import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Redirect, Stack, useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Image,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  View,
} from 'react-native';

import { GiftForm } from '@/components/gift-form';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { MaxContentWidth, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { useAuth } from '@/lib/auth-context';
import { wishlistApi, wishlistKeys, type Gift, type GiftInput } from '@/lib/wishlist-api';

function confirmDelete(onConfirm: () => void) {
  if (Platform.OS === 'web') {
    // Alert.alert is a no-op on react-native-web.
    if (window.confirm('Delete this gift?')) onConfirm();
    return;
  }
  Alert.alert('Delete gift', 'Delete this gift? This cannot be undone.', [
    { text: 'Cancel', style: 'cancel' },
    { text: 'Delete', style: 'destructive', onPress: onConfirm },
  ]);
}

export default function GiftDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const giftId = Number(id);
  const theme = useTheme();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { isAuthenticated } = useAuth();
  const [isEditing, setIsEditing] = useState(false);

  const giftQuery = useQuery({
    queryKey: wishlistKeys.gift(giftId),
    queryFn: () => wishlistApi.getGift(giftId),
    enabled: Number.isFinite(giftId) && isAuthenticated === true,
  });

  const updateMutation = useMutation({
    mutationFn: (input: GiftInput) => wishlistApi.updateGift(giftId, input),
    onSuccess: ({ gift }) => {
      queryClient.setQueryData<{ gift: Gift }>(wishlistKeys.gift(giftId), { gift });
      queryClient.invalidateQueries({ queryKey: wishlistKeys.gifts() });
      setIsEditing(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => wishlistApi.deleteGift(giftId),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: wishlistKeys.gift(giftId) });
      queryClient.invalidateQueries({ queryKey: wishlistKeys.gifts() });
      router.back();
    },
  });

  if (isAuthenticated === false) {
    return <Redirect href="/login" />;
  }

  if (giftQuery.isPending) {
    return (
      <ThemedView style={styles.centered}>
        <ActivityIndicator />
      </ThemedView>
    );
  }

  if (giftQuery.isError) {
    return (
      <ThemedView style={styles.centered}>
        <ThemedText themeColor="textSecondary">
          {giftQuery.error instanceof Error ? giftQuery.error.message : 'Couldn’t load gift.'}
        </ThemedText>
        <Pressable style={styles.button} onPress={() => giftQuery.refetch()}>
          <ThemedText type="smallBold" style={styles.buttonText}>
            Retry
          </ThemedText>
        </Pressable>
      </ThemedView>
    );
  }

  const gift = giftQuery.data.gift;
  const busy = updateMutation.isPending || deleteMutation.isPending;

  return (
    <ThemedView style={styles.container}>
      <Stack.Screen options={{ title: gift.title }} />
      <KeyboardAvoidingView
        style={styles.container}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <ScrollView contentContainerStyle={styles.scrollContent}>
          {isEditing ? (
            <>
              <GiftForm
                initialTitle={gift.title}
                initialBody={gift.body}
                existingImageUrl={gift.image_url}
                submitLabel="Save Changes"
                submitting={updateMutation.isPending}
                errorMessage={
                  updateMutation.isError
                    ? updateMutation.error instanceof Error
                      ? updateMutation.error.message
                      : 'Failed to save gift.'
                    : null
                }
                onSubmit={(input) => updateMutation.mutate(input)}
              />
              <Pressable
                style={[styles.buttonSecondary, { backgroundColor: theme.backgroundElement }]}
                disabled={busy}
                onPress={() => setIsEditing(false)}
              >
                <ThemedText type="smallBold">Cancel</ThemedText>
              </Pressable>
            </>
          ) : (
            <>
              {gift.image_url ? (
                <Image source={{ uri: gift.image_url }} style={styles.image} resizeMode="cover" />
              ) : null}
              <ThemedText type="subtitle">{gift.title}</ThemedText>
              <ThemedText>{gift.body}</ThemedText>
              {gift.timestamp ? (
                <ThemedText type="small" themeColor="textSecondary">
                  Added {new Date(gift.timestamp).toLocaleDateString()}
                </ThemedText>
              ) : null}

              <View style={styles.actions}>
                <Pressable
                  style={[styles.button, busy && styles.buttonDisabled]}
                  disabled={busy}
                  onPress={() => setIsEditing(true)}
                >
                  <ThemedText type="smallBold" style={styles.buttonText}>
                    Edit
                  </ThemedText>
                </Pressable>
                <Pressable
                  style={[styles.buttonDanger, busy && styles.buttonDisabled]}
                  disabled={busy}
                  onPress={() => confirmDelete(() => deleteMutation.mutate())}
                >
                  <ThemedText type="smallBold" style={styles.buttonText}>
                    {deleteMutation.isPending ? 'Deleting…' : 'Delete'}
                  </ThemedText>
                </Pressable>
              </View>
              {deleteMutation.isError ? (
                <ThemedText type="small" style={styles.error}>
                  {deleteMutation.error instanceof Error
                    ? deleteMutation.error.message
                    : 'Failed to delete gift.'}
                </ThemedText>
              ) : null}
            </>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.three,
  },
  scrollContent: {
    padding: Spacing.three,
    gap: Spacing.three,
    maxWidth: MaxContentWidth,
    width: '100%',
    alignSelf: 'center',
  },
  image: {
    width: '100%',
    height: 240,
    borderRadius: Spacing.two,
  },
  actions: {
    flexDirection: 'row',
    gap: Spacing.two,
    marginTop: Spacing.two,
  },
  button: {
    flex: 1,
    backgroundColor: '#3c87f7',
    borderRadius: Spacing.two,
    paddingVertical: Spacing.three,
    paddingHorizontal: Spacing.three,
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonDanger: {
    flex: 1,
    backgroundColor: '#d64545',
    borderRadius: Spacing.two,
    paddingVertical: Spacing.three,
    paddingHorizontal: Spacing.three,
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonSecondary: {
    borderRadius: Spacing.two,
    paddingVertical: Spacing.three,
    paddingHorizontal: Spacing.three,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: Spacing.two,
  },
  buttonDisabled: {
    opacity: 0.5,
  },
  buttonText: {
    color: '#ffffff',
  },
  error: {
    color: '#d64545',
  },
});
