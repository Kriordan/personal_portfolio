import { Host, TextInput, type TextInputProps } from '@expo/ui';
import type { PropsWithChildren } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { ThemedText } from './themed-text';
import { JobToolbarIcon } from './job-toolbar-icon';
import { fillWidth } from './native-width';
import { useTheme } from '@/hooks/use-theme';

export function JobTextAction({
  label,
  accessibilityLabel,
  onPress,
  disabled,
  expanded,
}: {
  label: string;
  accessibilityLabel?: string;
  onPress(): void;
  disabled?: boolean;
  expanded?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      accessibilityState={{ disabled: !!disabled, expanded }}
      disabled={disabled}
      onPress={onPress}
      style={[styles.action, disabled && styles.disabled]}
    >
      <ThemedText themeColor="accent">{label}</ThemedText>
    </Pressable>
  );
}

export function JobInfoButton({
  label,
  onPress,
  expanded,
}: {
  label: string;
  onPress(): void;
  expanded?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ expanded }}
      onPress={onPress}
      style={styles.info}
    >
      <JobToolbarIcon name="info" />
    </Pressable>
  );
}

/** A native observable input in a measured Host, with a semantic RN label. */
export function JobFormField({
  label,
  ...props
}: TextInputProps & { label: string }) {
  const theme = useTheme();
  return (
    <View style={styles.field}>
      <ThemedText type="smallBold">{label}</ThemedText>
      <View
        style={[
          styles.input,
          {
            backgroundColor: theme.backgroundElement,
            borderColor: theme.backgroundSelected,
          },
        ]}
      >
        <Host matchContents={{ vertical: true }} seedColor={theme.accent}>
          <TextInput
            {...props}
            {...fillWidth}
            placeholder={props.placeholder ?? label}
            style={{ ...fillWidth.style, paddingVertical: 8 }}
          />
        </Host>
      </View>
    </View>
  );
}

export function JobChoice({
  label,
  value,
  selected,
  multiple,
  disabled,
  onPress,
}: {
  label: string;
  value?: string;
  selected: boolean;
  multiple?: boolean;
  disabled?: boolean;
  onPress(): void;
}) {
  const theme = useTheme();
  return (
    <Pressable
      accessibilityRole={multiple ? 'checkbox' : 'radio'}
      accessibilityLabel={value ? `${label}: ${value}` : label}
      accessibilityState={{ checked: selected, disabled: !!disabled }}
      disabled={disabled}
      onPress={onPress}
      style={[
        styles.choice,
        { backgroundColor: theme.backgroundElement },
        disabled && styles.disabled,
      ]}
    >
      <View style={styles.mark}>
        <JobToolbarIcon name={selected ? 'selected' : 'unselected'} />
      </View>
      <View style={styles.grow}>
        <ThemedText
          type={value ? 'small' : 'default'}
          themeColor={value ? 'textSecondary' : 'text'}
        >
          {label}
        </ThemedText>
        {value ? <ThemedText>{value}</ThemedText> : null}
      </View>
    </Pressable>
  );
}

export function JobFormSection({
  title,
  children,
}: PropsWithChildren<{ title: string }>) {
  return (
    <View style={styles.section}>
      <ThemedText type="subtitle" accessibilityRole="header">
        {title}
      </ThemedText>
      {children}
    </View>
  );
}

export const jobFormStyles = StyleSheet.create({
  fill: { flex: 1 },
  hidden: { display: 'none' },
  content: {
    padding: 20,
    gap: 24,
    width: '100%',
    maxWidth: 720,
    alignSelf: 'center',
    paddingBottom: 32,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 12,
  },
  spread: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
    flexWrap: 'wrap',
  },
  group: { gap: 12 },
  compact: { gap: 4 },
  grow: { flex: 1 },
});
const styles = StyleSheet.create({
  action: {
    minHeight: 48,
    minWidth: 48,
    maxWidth: '100%',
    flexShrink: 1,
    justifyContent: 'center',
    paddingHorizontal: 4,
    alignSelf: 'flex-start',
  },
  info: {
    minHeight: 48,
    minWidth: 48,
    alignItems: 'center',
    justifyContent: 'center',
  },
  field: { gap: 6 },
  input: { borderRadius: 12, paddingHorizontal: 12, borderWidth: 1 },
  choice: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
    padding: 12,
    borderRadius: 12,
    minHeight: 48,
  },
  mark: { paddingTop: 2 },
  grow: { flex: 1 },
  section: { gap: 12 },
  disabled: { opacity: 0.5 },
});
