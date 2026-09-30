import { useRouter } from 'expo-router';
import { useState } from 'react';
import { RefreshControl, SectionList, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { NativeField, NativeFormSheet } from '@/components/native-form';
import {
  InlineError,
  NativeAction,
  NavRow,
  PageHeading,
  ScreenState,
  SectionHeading,
  screenStyles,
} from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { useCreateList, useListsOverview } from '@/hooks/use-lists';
import { useSubmission } from '@/hooks/use-submission';
import { useNativeText } from '@/hooks/use-native-text';
import { useTheme } from '@/hooks/use-theme';

export default function ListsScreen() {
  const lists = useListsOverview();
  const create = useCreateList();
  const submission = useSubmission();
  const router = useRouter();
  const theme = useTheme();
  const [presented, setPresented] = useState(false);
  const title = useNativeText();
  const submit = () => {
    const currentTitle = title.read();
    if (!currentTitle.trim()) return;
    void submission.run(async () => {
      const result = await create.mutateAsync(currentTitle.trim());
      title.clear();
      setPresented(false);
      router.push(`/lists/${result.list.id}`);
    });
  };
  if (!lists.data && lists.isPending)
    return (
      <ScreenState
        loading={!lists.isPaused}
        title={lists.isPaused ? 'You’re offline' : 'Loading your lists'}
        message={lists.isPaused ? 'Reconnect to load Grocery.' : undefined}
      />
    );
  if (!lists.data)
    return (
      <ScreenState
        title="Couldn’t load Grocery"
        message="Check your connection and try again."
        onRetry={() => void lists.refetch()}
      />
    );

  return (
    <SafeAreaView
      edges={['left', 'right', 'bottom']}
      style={[styles.screen, { backgroundColor: theme.background }]}
    >
      <SectionList
        sections={[
          {
            title: 'Your lists',
            data: lists.data.owned,
            empty: 'Your next shop starts here. Create your first list.',
          },
          {
            title: 'Shared with you',
            data: lists.data.shared,
            empty: 'Lists shared with your account will appear here.',
          },
        ]}
        keyExtractor={(list) => String(list.id)}
        contentContainerStyle={screenStyles.collection}
        contentInsetAdjustmentBehavior="automatic"
        stickySectionHeadersEnabled={false}
        refreshControl={
          <RefreshControl
            refreshing={lists.isRefetching}
            onRefresh={() => void lists.refetch()}
          />
        }
        ListHeaderComponent={
          <View style={screenStyles.gap}>
            <PageHeading
              title="A good shop starts with a list."
              subtitle="Keep your essentials together, wherever you are."
            />
            <NativeAction
              label="Create a list"
              onPress={() => setPresented(true)}
            />
            {lists.isError ? (
              <InlineError
                message="Couldn’t refresh. These are the last loaded lists."
                onRetry={() => void lists.refetch()}
              />
            ) : null}
          </View>
        }
        renderSectionHeader={({ section }) => (
          <SectionHeading>{section.title}</SectionHeading>
        )}
        renderItem={({ item }) => (
          <View style={styles.row}>
            <NavRow title={item.title} href={`/lists/${item.id}`} />
          </View>
        )}
        renderSectionFooter={({ section }) =>
          section.data.length ? null : (
            <ThemedText style={styles.empty} themeColor="textSecondary">
              {section.empty}
            </ThemedText>
          )
        }
      />
      <NativeFormSheet
        title="New grocery list"
        presented={presented}
        onDismiss={() => setPresented(false)}
        onSubmit={() => submit()}
        submitLabel="Create list"
        pending={submission.pending}
        disabled={!title.text.trim()}
        error={submission.error}
      >
        <NativeField
          label="List name"
          placeholder="For example, Weekly groceries"
          {...title.input}
          editable={!submission.pending}
          returnKeyType="done"
          onSubmitEditing={submit}
        />
      </NativeFormSheet>
    </SafeAreaView>
  );
}
const styles = StyleSheet.create({
  screen: { flex: 1 },
  row: { marginBottom: 8 },
  empty: { paddingVertical: 16, paddingHorizontal: 4 },
});
