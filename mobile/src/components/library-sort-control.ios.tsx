import { Host, Label, Menu, Picker, Text, VStack } from '@expo/ui/swift-ui';
import { accessibilityLabel, disabled, fixedSize, foregroundStyle, frame, labelsHidden, padding, pickerStyle, tag } from '@expo/ui/swift-ui/modifiers';

import type { useLibrarySort } from '@/hooks/use-library-sort';
import { useTheme } from '@/hooks/use-theme';

export function LibrarySortControl({ sort }: { sort: ReturnType<typeof useLibrarySort> }) {
  const theme = useTheme();
  const selectedLabel = sort.options.find((option) => option.value === sort.value)?.label;
  return <Host matchContents={{ vertical: true }} style={{ width: '100%' }}>
    <VStack alignment="leading" spacing={6} modifiers={[frame({ maxWidth: Infinity, alignment: 'leading' }), padding({ vertical: 8 })]}>
      <Text modifiers={[foregroundStyle(theme.text)]}>Sort</Text>
      {/* A custom menu label measures every wrapped line; the menu-style Picker can report only one line to Host. */}
      <Menu modifiers={[disabled(!sort.ready), accessibilityLabel(`Sort: ${selectedLabel}`)]} label={
        <Label systemImage="arrow.up.arrow.down" modifiers={[frame({ minHeight: 44, alignment: 'leading' })]}>
          <Text modifiers={[fixedSize({ horizontal: false, vertical: true })]}>{selectedLabel}</Text>
        </Label>
      }>
        <Picker label="Sort" selection={sort.value} onSelectionChange={sort.select}
          modifiers={[pickerStyle('inline'), labelsHidden()]}>
          {sort.options.map((option) => <Text key={option.value} modifiers={[tag(option.value)]}>{option.label}</Text>)}
        </Picker>
      </Menu>
    </VStack>
  </Host>;
}
