import { Host, TextInput } from '@expo/ui';
import { useState } from 'react';
import { NavRow, PageHeading, Screen } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { fillWidth } from '@/components/native-width';
import { mobileTools } from '@/constants/tools';
import { useTheme } from '@/hooks/use-theme';

export default function ToolsScreen() {
  const [filter, setFilter] = useState('');
  const theme = useTheme();
  const tools = mobileTools.filter((tool) =>
    tool.title.toLowerCase().includes(filter.trim().toLowerCase()),
  );
  return (
    <Screen tab>
      <PageHeading
        title="Tools"
        subtitle="Small things, thoughtfully organized."
      />
      <Host matchContents={{ vertical: true }} seedColor={theme.accent}>
        <TextInput
          {...fillWidth}
          placeholder="Filter tools by name"
          onChangeText={setFilter}
          autoCorrect={false}
          returnKeyType="done"
          style={{
            ...fillWidth.style,
            padding: 16,
            backgroundColor: theme.backgroundElement,
            borderRadius: 14,
          }}
          textStyle={{ color: theme.text }}
        />
      </Host>
      {tools.map((tool) => (
        <NavRow
          key={tool.href}
          title={tool.title}
          subtitle={tool.description}
          href={tool.href}
          badge={tool.badge}
        />
      ))}
      {tools.length === 0 ? (
        <ThemedText themeColor="textSecondary">
          No tools match “{filter}”. Try Grocery, Wishlist, Library, Learning,
          or Jobwizard.
        </ThemedText>
      ) : null}
    </Screen>
  );
}
