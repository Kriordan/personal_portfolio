import { View } from 'react-native';
import { JobToolbarIcon } from './job-toolbar-icon';
import { useTheme } from '@/hooks/use-theme';
import type { JobBrowseChoiceProps } from './job-browse-choice.types';

// Native platforms resolve their own menu files; web keeps the browser's keyboard-accessible select.
export function JobBrowseChoice<T extends string>({ label, value, options, onChange, icon }: JobBrowseChoiceProps<T>) {
  const theme = useTheme();
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
      <JobToolbarIcon name={icon} />
      <select aria-label={label} value={value} onChange={(event) => {
        const option = options.find((item) => item.value === event.target.value);
        if (option) onChange(option.value);
      }} style={{ minHeight: 44, font: 'inherit', fontSize: 17, border: 0, background: 'transparent', color: theme.accent }}>
        {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
    </View>
  );
}
