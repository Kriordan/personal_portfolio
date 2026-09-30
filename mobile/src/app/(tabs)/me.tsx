import { Button, FieldGroup, Host, Text } from '@expo/ui';
import { StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { InlineError, PageHeading } from '@/components/screen';
import { useSubmission } from '@/hooks/use-submission';
import { useTheme } from '@/hooks/use-theme';
import { useAuth } from '@/lib/auth-context';

export default function MeScreen() {
  const { user, signOut } = useAuth();
  const submission = useSubmission();
  const theme = useTheme();
  return (
    <SafeAreaView
      edges={['top', 'left', 'right']}
      style={[styles.screen, { backgroundColor: theme.background }]}
    >
      <View style={styles.heading}>
        <PageHeading title="Me" subtitle="Your personal space." />
        {submission.error ? <InlineError message={submission.error} /> : null}
      </View>
      <Host style={styles.form} seedColor={theme.accent}>
        <FieldGroup>
          <FieldGroup.Section title="Account">
            <Text>{user?.username ?? 'Account details unavailable'}</Text>
            <Text>
              {user?.email ?? 'Reconnect to load your account information.'}
            </Text>
            {user ? (
              <Text>
                {user.email_verified ? 'Email verified' : 'Email not verified'}
              </Text>
            ) : null}
          </FieldGroup.Section>
          <FieldGroup.Section>
            <Button
              variant="text"
              label={submission.pending ? 'Signing out…' : 'Sign out'}
              disabled={submission.pending}
              onPress={() => void submission.run(signOut)}
            />
          </FieldGroup.Section>
        </FieldGroup>
      </Host>
    </SafeAreaView>
  );
}
const styles = StyleSheet.create({
  screen: { flex: 1 },
  heading: { paddingHorizontal: 20 },
  form: { flex: 1 },
});
