import {
  BottomSheet,
  Button,
  Column,
  FieldGroup,
  Host,
  RNHostView,
  Text,
  TextInput,
  type TextInputProps,
} from '@expo/ui';
import type { ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';

import { InlineError, PageHeading } from '@/components/screen';
import { fillWidth } from '@/components/native-width';
import { useTheme } from '@/hooks/use-theme';

/** Native inputs share their live text with the form through useNativeText. */
export function NativeField({
  label,
  ...props
}: TextInputProps & { label: string }) {
  return (
    <Column
      spacing={6}
      {...fillWidth}
      style={{ ...fillWidth.style, paddingVertical: 4 }}
    >
      <Text>{label}</Text>
      <TextInput
        {...fillWidth}
        {...props}
        placeholder={props.placeholder ?? label}
        style={{ ...fillWidth.style, paddingVertical: 8 }}
      />
    </Column>
  );
}

/** Native fields live in a single Host; the sheet owns its scrolling and keyboard avoidance. */
export function NativeFormSheet({
  title,
  presented,
  onDismiss,
  children,
  onSubmit,
  submitLabel,
  pending,
  disabled,
  error,
}: {
  title: string;
  presented: boolean;
  onDismiss: () => void;
  children: ReactNode;
  onSubmit: () => void;
  submitLabel: string;
  pending: boolean;
  disabled?: boolean;
  error: string | null;
}) {
  const theme = useTheme();
  return (
    <BottomSheet
      isPresented={presented}
      onDismiss={onDismiss}
      snapPoints={['full']}
      contentPadding={0}
      containerColor={theme.background}
    >
      <RNHostView matchContents={false}>
        <View style={styles.sheet}>
          <View style={styles.heading}>
            <PageHeading title={title} />
            {error ? <InlineError message={error} /> : null}
          </View>
          <Host style={styles.form} seedColor={theme.accent}>
            <FieldGroup>
              <FieldGroup.Section>{children}</FieldGroup.Section>
              <FieldGroup.Section>
                <Button
                  label={pending ? 'Saving…' : submitLabel}
                  onPress={onSubmit}
                  disabled={pending || disabled}
                />
                <Button
                  label="Close"
                  variant="text"
                  onPress={onDismiss}
                  disabled={pending}
                />
              </FieldGroup.Section>
            </FieldGroup>
          </Host>
        </View>
      </RNHostView>
    </BottomSheet>
  );
}
const styles = StyleSheet.create({
  sheet: { flex: 1 },
  heading: { paddingHorizontal: 20, paddingTop: 16 },
  form: { flex: 1 },
});
