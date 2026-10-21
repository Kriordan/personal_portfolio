import { Column, Host, Picker, Text } from '@expo/ui';
import { fillWidth } from '@/components/native-width';
import { useTheme } from '@/hooks/use-theme';
import type { NativeChoiceProps } from './native-choice.types';

export function NativeChoice<T extends string>({
  label,
  value,
  options,
  onChange,
  enabled = true,
}: NativeChoiceProps<T>) {
  const theme = useTheme();
  return (
    <Host matchContents={{ vertical: true }} style={{ width: '100%' }}>
      <Column
        {...fillWidth}
        spacing={6}
        style={{ ...fillWidth.style, paddingVertical: 8 }}
      >
        <Text textStyle={{ color: theme.text }}>{label}</Text>
        <Picker
          selectedValue={value}
          onValueChange={onChange}
          enabled={enabled}
        >
          {options.map((option) => (
            <Picker.Item
              key={option.value}
              label={option.label}
              value={option.value}
            />
          ))}
        </Picker>
      </Column>
    </Host>
  );
}
