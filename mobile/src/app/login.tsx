import { Button, Column, Host } from '@expo/ui';

import { NativeField } from '@/components/native-form';
import { PasswordField } from '@/components/password-field';
import { fillWidth } from '@/components/native-width';
import { Card, InlineError, PageHeading, Screen } from '@/components/screen';
import { useSubmission } from '@/hooks/use-submission';
import { useNativeText } from '@/hooks/use-native-text';
import { useTheme } from '@/hooks/use-theme';
import { useAuth } from '@/lib/auth-context';

export default function LoginScreen() {
  const { signIn } = useAuth();
  const theme = useTheme();
  const email = useNativeText();
  const password = useNativeText();
  const submission = useSubmission();
  const canSubmit =
    !!email.text.trim() && !!password.text && !submission.pending;
  const submit = () => {
    const currentEmail = email.read().trim();
    const currentPassword = password.read();
    if (currentEmail && currentPassword && !submission.pending)
      void submission.run(() => signIn(currentEmail, currentPassword));
  };
  return (
    <Screen
      tab
      contentContainerStyle={{ flexGrow: 1, justifyContent: 'center' }}
    >
      <PageHeading
        eyebrow="PERSONAL PORTFOLIO"
        title="Welcome back."
        subtitle="Your everyday tools, all in one place."
      />
      <Card>
        <Host matchContents={{ vertical: true }} seedColor={theme.accent}>
          <Column spacing={20} {...fillWidth}>
            <NativeField
              label="Email"
              {...email.input}
              keyboardType="email-address"
              autoComplete="email"
              autoCapitalize="none"
              autoCorrect={false}
              editable={!submission.pending}
            />
            <PasswordField
              {...password.input}
              editable={!submission.pending}
              onSubmit={submit}
            />
            <Button
              {...fillWidth}
              label={submission.pending ? 'Signing in…' : 'Sign in'}
              onPress={() => submit()}
              disabled={!canSubmit}
              style={{ ...fillWidth.style, paddingVertical: 8 }}
            />
          </Column>
        </Host>
        {submission.error ? <InlineError message={submission.error} /> : null}
      </Card>
    </Screen>
  );
}
