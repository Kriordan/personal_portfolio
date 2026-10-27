import { useState } from 'react';
import { Modal, Pressable, StyleSheet, View } from 'react-native';
import { ThemedText } from './themed-text';
import { jobActions, type JobActionsMenuProps } from './job-actions-menu.types';
import { useTheme } from '@/hooks/use-theme';

// Web fallback; iOS and Android use the platform menu in the native file.
export function JobActionsMenu(props: JobActionsMenuProps) {
  const [open, setOpen] = useState(false);
  const theme = useTheme();
  return (
    <>
      <Pressable accessibilityRole="button" accessibilityLabel="More job actions"
        accessibilityState={{ expanded: open }} onPress={() => setOpen(true)} style={styles.trigger}>
        <ThemedText themeColor="accent" style={styles.dots}>⋯</ThemedText>
      </Pressable>
      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <View style={styles.overlay}>
          <Pressable accessibilityRole="button" accessibilityLabel="Dismiss job actions"
            onPress={() => setOpen(false)} style={StyleSheet.absoluteFill} />
          <View accessibilityViewIsModal style={[styles.menu, { backgroundColor: theme.backgroundElement }]}>
            <ThemedText type="smallBold">Job actions</ThemedText>
            {jobActions(props).map((action) => (
              <Pressable key={action.id} accessibilityRole="button" disabled={!action.enabled}
                accessibilityState={{ disabled: !action.enabled }}
                style={[styles.item, !action.enabled && { opacity: 0.4 }]}
                onPress={() => { setOpen(false); props.onAction(action.id); }}>
                <ThemedText>{action.title}</ThemedText>
              </Pressable>
            ))}
            <Pressable accessibilityRole="button" onPress={() => setOpen(false)} style={styles.item}>
              <ThemedText themeColor="accent">Cancel</ThemedText>
            </Pressable>
          </View>
        </View>
      </Modal>
    </>
  );
}
const styles = StyleSheet.create({
  trigger: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  dots: { fontSize: 28, lineHeight: 32, fontWeight: '600' },
  overlay: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24, backgroundColor: '#0006' },
  menu: { width: '100%', maxWidth: 320, padding: 20, borderRadius: 16 },
  item: { minHeight: 44, paddingVertical: 10 },
});
