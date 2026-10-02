import { Button, Host } from '@expo/ui';
import { useRouter, type Href } from 'expo-router';
import type { PropsWithChildren } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  View,
  type ScrollViewProps,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ThemedText } from '@/components/themed-text';
import { fillWidth } from '@/components/native-width';
import { MaxContentWidth } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

export function Screen({
  children,
  tab = false,
  ...props
}: ScrollViewProps & { tab?: boolean }) {
  const theme = useTheme();
  return (
    <SafeAreaView
      edges={tab ? ['top', 'left', 'right'] : ['left', 'right', 'bottom']}
      style={[styles.fill, { backgroundColor: theme.background }]}
    >
      <KeyboardAvoidingView
        behavior={Platform.OS === 'android' ? 'height' : undefined}
        style={styles.fill}
      >
        <ScrollView
          contentInsetAdjustmentBehavior="automatic"
          keyboardShouldPersistTaps="handled"
          automaticallyAdjustKeyboardInsets
          {...props}
          contentContainerStyle={[styles.content, props.contentContainerStyle]}
        >
          {children}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

export function PageHeading({
  title,
  subtitle,
  eyebrow,
}: {
  title: string;
  subtitle?: string;
  eyebrow?: string;
}) {
  return (
    <View style={styles.heading}>
      {eyebrow ? (
        <ThemedText type="smallBold" themeColor="accent">
          {eyebrow}
        </ThemedText>
      ) : null}
      <ThemedText type="title" accessibilityRole="header">
        {title}
      </ThemedText>
      {subtitle ? (
        <ThemedText themeColor="textSecondary">{subtitle}</ThemedText>
      ) : null}
    </View>
  );
}

export function Card({ children }: PropsWithChildren) {
  const theme = useTheme();
  return (
    <View style={[styles.card, { backgroundColor: theme.backgroundElement }]}>
      {children}
    </View>
  );
}

export function SectionHeading({ children }: { children: string }) {
  return (
    <ThemedText
      type="subtitle"
      accessibilityRole="header"
      style={styles.sectionHeading}
    >
      {children}
    </ThemedText>
  );
}

export function NativeAction({
  label,
  onPress,
  disabled,
  secondary = false,
}: {
  label: string;
  onPress: () => void;
  disabled?: boolean;
  secondary?: boolean;
}) {
  const theme = useTheme();
  return (
    <Host
      matchContents={{ vertical: true }}
      seedColor={theme.accent}
      style={styles.action}
    >
      <Button
        {...fillWidth}
        label={label}
        onPress={onPress}
        disabled={disabled}
        variant={secondary ? 'outlined' : 'filled'}
        style={{ ...fillWidth.style, paddingVertical: 8 }}
      />
    </Host>
  );
}

export function NavRow({
  title,
  subtitle,
  href,
  badge,
}: {
  title: string;
  subtitle?: string;
  href: Href;
  badge?: string;
}) {
  const theme = useTheme();
  const router = useRouter();
  return (
    <Pressable
      accessibilityRole="link"
      accessibilityLabel={subtitle ? `${title}. ${subtitle}` : title}
      onPress={() => router.push(href)}
      style={({ pressed }) => [
        styles.navRow,
        {
          backgroundColor: pressed
            ? theme.backgroundSelected
            : theme.backgroundElement,
        },
      ]}
    >
      {badge ? (
        <View style={[styles.badge, { backgroundColor: theme.accentSoft }]}>
          <ThemedText themeColor="accent" type="smallBold">
            {badge}
          </ThemedText>
        </View>
      ) : null}
      <View style={styles.rowBody}>
        <ThemedText style={styles.rowTitle}>{title}</ThemedText>
        {subtitle ? (
          <ThemedText type="small" themeColor="textSecondary">
            {subtitle}
          </ThemedText>
        ) : null}
      </View>
      <ThemedText themeColor="textSecondary" accessible={false}>
        ›
      </ThemedText>
    </Pressable>
  );
}

export function InlineError({
  message,
  onRetry,
  retryLabel = 'Try again',
}: {
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
}) {
  return (
    <View style={styles.message}>
      <ThemedText
        themeColor="danger"
        accessibilityRole="alert"
        accessibilityLiveRegion="polite"
      >
        {message}
      </ThemedText>
      {onRetry ? (
        <NativeAction label={retryLabel} onPress={onRetry} secondary />
      ) : null}
    </View>
  );
}

export function ScreenState({
  title,
  message,
  loading = false,
  onRetry,
}: {
  title: string;
  message?: string;
  loading?: boolean;
  onRetry?: () => void;
}) {
  const theme = useTheme();
  return (
    <ScrollView
      style={[styles.fill, { backgroundColor: theme.background }]}
      contentContainerStyle={styles.state}
      contentInsetAdjustmentBehavior="automatic"
    >
      {loading ? <ActivityIndicator size="large" color={theme.accent} /> : null}
      <ThemedText type="subtitle" accessibilityRole="header">
        {title}
      </ThemedText>
      {message ? (
        <ThemedText themeColor="textSecondary" style={styles.centerText}>
          {message}
        </ThemedText>
      ) : null}
      {onRetry ? <NativeAction label="Try again" onPress={onRetry} /> : null}
    </ScrollView>
  );
}

export const screenStyles = StyleSheet.create({
  collection: {
    paddingHorizontal: 20,
    paddingTop: 12,
    paddingBottom: 32,
    maxWidth: MaxContentWidth,
    width: '100%',
    alignSelf: 'center',
  },
  gap: { gap: 12 },
});
const styles = StyleSheet.create({
  fill: { flex: 1 },
  content: {
    padding: 20,
    paddingBottom: 32,
    gap: 16,
    width: '100%',
    maxWidth: MaxContentWidth,
    alignSelf: 'center',
  },
  heading: { gap: 6, marginTop: 8, marginBottom: 8 },
  card: { borderRadius: 20, padding: 20, gap: 12 },
  sectionHeading: { marginTop: 12, marginBottom: 4 },
  action: { width: '100%' },
  navRow: {
    minHeight: 64,
    borderRadius: 16,
    padding: 16,
    gap: 14,
    flexDirection: 'row',
    alignItems: 'center',
  },
  rowBody: { flex: 1, gap: 3 },
  rowTitle: { fontWeight: '600' },
  badge: {
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 12,
  },
  message: { gap: 8, paddingVertical: 8 },
  state: {
    flexGrow: 1,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 16,
    padding: 32,
  },
  centerText: { textAlign: 'center' },
});
