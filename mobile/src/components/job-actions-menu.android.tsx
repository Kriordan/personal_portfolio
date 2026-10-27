import { MenuView, type MenuComponentRef } from '@expo/ui/community/menu';
import { useRef } from 'react';
import { StyleSheet, View } from 'react-native';
import { ThemedText } from './themed-text';
import { jobActions, type JobActionsMenuProps } from './job-actions-menu.types';
import { useTheme } from '@/hooks/use-theme';

export function JobActionsMenu(props: JobActionsMenuProps) {
  const ref = useRef<MenuComponentRef>(null);
  const theme = useTheme();
  const actions = jobActions(props);
  return (
    <MenuView
      ref={ref}
      style={styles.trigger}
      actions={actions.map(({ enabled, ...action }) => ({
        ...action,
        attributes: { disabled: !enabled },
      }))}
      onPressAction={({ nativeEvent }) => {
        const action = actions.find(({ id }) => id === nativeEvent.event);
        if (action?.enabled) props.onAction(action.id);
      }}
    >
      <View
        style={[styles.trigger, styles.outline, { borderColor: theme.border, backgroundColor: theme.backgroundElement }]}
        accessible
        accessibilityRole="button"
        accessibilityLabel="More job actions"
        accessibilityHint="Show listing, copy link, edit or archive this job"
        accessibilityActions={[{ name: 'activate' }]}
        onAccessibilityAction={() => ref.current?.show()}
      >
        <ThemedText accessible={false} themeColor="accent" style={styles.dots}>⋯</ThemedText>
      </View>
    </MenuView>
  );
}
const styles = StyleSheet.create({
  trigger: { width: 48, height: 48, alignItems: 'center', justifyContent: 'center' },
  outline: { borderWidth: 1, borderRadius: 12 },
  dots: { fontSize: 28, lineHeight: 32, fontWeight: '600' },
});
