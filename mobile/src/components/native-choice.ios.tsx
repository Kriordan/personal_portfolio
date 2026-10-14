import { Host, Label, Menu, Picker, Text, VStack } from '@expo/ui/swift-ui';
import {
  accessibilityLabel,
  disabled,
  fixedSize,
  foregroundStyle,
  frame,
  labelsHidden,
  padding,
  pickerStyle,
  tag,
} from '@expo/ui/swift-ui/modifiers';
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
  const selected = options.find((option) => option.value === value)?.label;
  return (
    <Host matchContents={{ vertical: true }} style={{ width: '100%' }}>
      <VStack
        alignment="leading"
        spacing={6}
        modifiers={[
          frame({ maxWidth: Infinity, alignment: 'leading' }),
          padding({ vertical: 8 }),
        ]}
      >
        <Text modifiers={[foregroundStyle(theme.text)]}>{label}</Text>
        <Menu
          modifiers={[
            disabled(!enabled),
            accessibilityLabel(`${label}: ${selected}`),
          ]}
          label={
            <Label
              systemImage="arrow.up.arrow.down"
              modifiers={[frame({ minHeight: 44, alignment: 'leading' })]}
            >
              <Text
                modifiers={[fixedSize({ horizontal: false, vertical: true })]}
              >
                {selected}
              </Text>
            </Label>
          }
        >
          <Picker
            label={label}
            selection={value}
            onSelectionChange={onChange}
            modifiers={[pickerStyle('inline'), labelsHidden()]}
          >
            {options.map((option) => (
              <Text key={option.value} modifiers={[tag(option.value)]}>
                {option.label}
              </Text>
            ))}
          </Picker>
        </Menu>
      </VStack>
    </Host>
  );
}
