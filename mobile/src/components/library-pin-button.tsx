import { Pressable } from 'react-native';
import { ThemedText } from '@/components/themed-text';

export function LibraryPinButton({ title, pinned, disabled, onPress }: { title: string; pinned: boolean; disabled: boolean; onPress: () => void }) {
  return <Pressable accessibilityRole="button" accessibilityLabel={`${pinned ? 'Unpin' : 'Pin'} ${title}`} accessibilityHint="Changes only your account’s shortcuts" accessibilityState={{ disabled }} disabled={disabled} onPress={onPress}
    style={({ pressed }) => ({ minHeight: 44, paddingHorizontal: 16, justifyContent: 'center', opacity: disabled ? 0.5 : pressed ? 0.6 : 1 })}>
    <ThemedText type="smallBold" themeColor="accent">{pinned ? 'Unpin' : 'Pin'}</ThemedText>
  </Pressable>;
}
