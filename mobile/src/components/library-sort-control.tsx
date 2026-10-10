import { Column, Host, Picker, Text } from '@expo/ui';

import { fillWidth } from '@/components/native-width';
import type { useLibrarySort } from '@/hooks/use-library-sort';
import { useTheme } from '@/hooks/use-theme';

export function LibrarySortControl({ sort }: { sort: ReturnType<typeof useLibrarySort> }) {
  const theme = useTheme();
  return <Host matchContents={{ vertical: true }} style={{ width: '100%' }}>
    <Column {...fillWidth} spacing={6} style={{ ...fillWidth.style, paddingVertical: 8 }}>
      <Text textStyle={{ color: theme.text }}>Sort</Text>
      <Picker selectedValue={sort.value} onValueChange={sort.select} enabled={sort.ready}>
        {sort.options.map((option) => <Picker.Item key={option.value} label={option.label} value={option.value} />)}
      </Picker>
    </Column>
  </Host>;
}
