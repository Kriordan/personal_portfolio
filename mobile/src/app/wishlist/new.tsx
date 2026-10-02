import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet } from 'react-native';

import { GiftForm } from '@/components/gift-form';
import { ThemedView } from '@/components/themed-view';
import { MaxContentWidth, Spacing } from '@/constants/theme';
import { wishlistApi, wishlistKeys, type GiftInput } from '@/lib/wishlist-api';

export default function NewGiftScreen() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const createMutation = useMutation({
    mutationFn: (input: GiftInput) => wishlistApi.createGift(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: wishlistKeys.gifts() });
      router.back();
    },
  });

  return (
    <ThemedView style={styles.container}>
      <KeyboardAvoidingView
        style={styles.container}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <ScrollView contentContainerStyle={styles.scrollContent}>
          <GiftForm
            submitLabel="Add Gift"
            submitting={createMutation.isPending}
            errorMessage={
              createMutation.isError
                ? createMutation.error instanceof Error
                  ? createMutation.error.message
                  : 'Failed to add gift.'
                : null
            }
            onSubmit={(input) => createMutation.mutate(input)}
          />
        </ScrollView>
      </KeyboardAvoidingView>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  scrollContent: {
    padding: Spacing.three,
    maxWidth: MaxContentWidth,
    width: '100%',
    alignSelf: 'center',
  },
});
