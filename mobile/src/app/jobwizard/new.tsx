import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Redirect, useRouter } from 'expo-router';
import { useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  TextInput,
} from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { MaxContentWidth, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { useAuth } from '@/lib/auth-context';
import { jobwizardApi, jobwizardKeys, type JobInput } from '@/lib/jobwizard-api';

export default function NewJobScreen() {
  const router = useRouter();
  const theme = useTheme();
  const queryClient = useQueryClient();
  const { isAuthenticated } = useAuth();

  const [title, setTitle] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [listingUrl, setListingUrl] = useState('');

  const createMutation = useMutation({
    mutationFn: (input: JobInput) => jobwizardApi.createJob(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: jobwizardKeys.jobs() });
      router.back();
    },
  });

  if (isAuthenticated === false) {
    return <Redirect href="/login" />;
  }

  const submitting = createMutation.isPending;
  const canSubmit =
    title.trim().length > 0 &&
    companyName.trim().length > 0 &&
    listingUrl.trim().length > 0 &&
    !submitting;

  const inputStyle = [
    styles.input,
    { color: theme.text, backgroundColor: theme.backgroundElement },
  ];

  return (
    <ThemedView style={styles.container}>
      <KeyboardAvoidingView
        style={styles.container}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <ScrollView contentContainerStyle={styles.scrollContent}>
          <TextInput
            style={inputStyle}
            placeholder="Job title"
            placeholderTextColor={theme.textSecondary}
            value={title}
            onChangeText={setTitle}
            editable={!submitting}
          />
          <TextInput
            style={inputStyle}
            placeholder="Company"
            placeholderTextColor={theme.textSecondary}
            value={companyName}
            onChangeText={setCompanyName}
            editable={!submitting}
          />
          <TextInput
            style={inputStyle}
            placeholder="Listing URL"
            placeholderTextColor={theme.textSecondary}
            value={listingUrl}
            onChangeText={setListingUrl}
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="url"
            editable={!submitting}
          />

          <Pressable
            style={[styles.button, !canSubmit && styles.buttonDisabled]}
            disabled={!canSubmit}
            onPress={() =>
              createMutation.mutate({
                title: title.trim(),
                company_name: companyName.trim(),
                listing_url: listingUrl.trim(),
              })
            }
          >
            <ThemedText type="smallBold" style={styles.buttonText}>
              {submitting ? 'Saving…' : 'Add Job'}
            </ThemedText>
          </Pressable>

          {submitting ? (
            <ThemedText type="small" themeColor="textSecondary">
              Capturing a screenshot of the listing. This can take a moment.
            </ThemedText>
          ) : null}

          {createMutation.isError ? (
            <ThemedText type="small" style={styles.error}>
              {createMutation.error instanceof Error
                ? createMutation.error.message
                : 'Failed to add job.'}
            </ThemedText>
          ) : null}
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
    gap: Spacing.two,
    maxWidth: MaxContentWidth,
    width: '100%',
    alignSelf: 'center',
  },
  input: {
    borderRadius: Spacing.two,
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.two,
    fontSize: 16,
  },
  button: {
    backgroundColor: '#3c87f7',
    borderRadius: Spacing.two,
    paddingVertical: Spacing.three,
    paddingHorizontal: Spacing.three,
    alignItems: 'center',
    justifyContent: 'center',
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
