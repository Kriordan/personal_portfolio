import { Host, Menu, Picker, Text } from '@expo/ui/swift-ui';
import { accessibilityLabel, fixedSize, frame, labelsHidden, pickerStyle, tag, tint } from '@expo/ui/swift-ui/modifiers';
import { useTheme } from '@/hooks/use-theme';
import type { JobBrowseChoiceProps } from './job-browse-choice.types';

export function JobBrowseChoice<T extends string>({ label, value, options, onChange, icon }: JobBrowseChoiceProps<T>) {
  const theme = useTheme();
  const selected = options.find((option) => option.value === value)?.label ?? label;
  return (
    <Host matchContents ignoreSafeArea="all" style={{ maxWidth: '100%' }}>
      <Menu label={selected} systemImage={icon === 'filter' ? 'line.3.horizontal.decrease' : 'arrow.up.arrow.down'}
        modifiers={[accessibilityLabel(`${label}: ${selected}`), fixedSize({ horizontal: false, vertical: true }), frame({ minHeight: 44 }), tint(theme.accent)]}>
        <Picker label={label} selection={value} onSelectionChange={onChange} modifiers={[pickerStyle('inline'), labelsHidden()]}>
          {options.map((option) => <Text key={option.value} modifiers={[tag(option.value)]}>{option.label}</Text>)}
        </Picker>
      </Menu>
    </Host>
  );
}
