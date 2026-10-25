import { Pressable, StyleSheet } from 'react-native';
import { ThemedText } from './themed-text';

export function SourceLink({ expanded, onPress, detail }: {
  expanded: boolean;
  onPress(): void;
  detail: number;
}) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`${expanded ? 'Hide' : 'Show'} source for detail ${detail}`}
      accessibilityState={{ expanded }}
      style={styles.link}
    >
      <ThemedText type="small" themeColor="accent" style={styles.text}>
        {expanded ? 'Hide source' : 'Source'}
      </ThemedText>
    </Pressable>
  );
}
const styles = StyleSheet.create({
  link: { alignSelf: 'flex-start', minWidth: 48, minHeight: 44, justifyContent: 'center' },
  text: { textDecorationLine: 'underline' },
});
