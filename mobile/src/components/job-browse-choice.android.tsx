import { MenuView, type MenuComponentRef } from '@expo/ui/community/menu';
import { useRef } from 'react';
import { View } from 'react-native';
import { JobToolbarIcon } from './job-toolbar-icon';
import { ThemedText } from './themed-text';
import type { JobBrowseChoiceProps } from './job-browse-choice.types';

export function JobBrowseChoice<T extends string>({ label, value, options, onChange, icon }: JobBrowseChoiceProps<T>) {
  const ref = useRef<MenuComponentRef>(null);
  const selected = options.find((option) => option.value === value)?.label ?? label;
  return (
    <MenuView ref={ref} style={{ maxWidth: '100%' }} actions={options.map((option) => ({ id: option.value, title: option.label, state: option.value === value ? 'on' : 'off' }))}
      onPressAction={({ nativeEvent }) => {
        const option = options.find((item) => item.value === nativeEvent.event);
        if (option) onChange(option.value);
      }}>
      <View accessible accessibilityRole="button" accessibilityLabel={`${label}: ${selected}`}
        accessibilityActions={[{ name: 'activate' }]} onAccessibilityAction={() => ref.current?.show()}
        style={{ minHeight: 48, flexDirection: 'row', alignItems: 'center', gap: 6 }}>
        <JobToolbarIcon name={icon} />
        <ThemedText themeColor="accent" style={{ flexShrink: 1 }}>{selected}</ThemedText>
      </View>
    </MenuView>
  );
}
