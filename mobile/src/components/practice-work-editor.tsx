import * as Crypto from 'expo-crypto';
import { useState } from 'react';
import {
  Alert,
  Keyboard,
  Platform,
  Pressable,
  StyleSheet,
  Switch,
  TextInput,
  View,
} from 'react-native';
import { LearningText } from './learning-content';
import { Card, NativeAction, SectionHeading } from './screen';
import { ThemedText } from './themed-text';
import { useTheme } from '@/hooks/use-theme';
import {
  ARTIFACT_LIMIT,
  BRIEF_ENTRY_COUNT,
  BRIEF_ENTRY_LIMIT,
  briefTypes,
  type BriefEntry,
  type WorkEdit,
} from '@/lib/practice-work-model';

export const briefLabels = {
  assumption: 'Assumption',
  question: 'Open question',
  decision: 'Decision',
  next_step: 'Next step',
};
function Choice({
  label,
  selected,
  disabled,
  onPress,
}: {
  label: string;
  selected: boolean;
  disabled?: boolean;
  onPress: () => void;
}) {
  const theme = useTheme();
  return (
    <Pressable
      accessibilityRole="radio"
      accessibilityLabel={label}
      accessibilityState={{ selected, disabled: !!disabled }}
      disabled={disabled}
      onPress={onPress}
      style={[
        styles.choice,
        {
          backgroundColor: selected
            ? theme.accentSoft
            : theme.backgroundElement,
        },
      ]}
    >
      <ThemedText
        type="smallBold"
        themeColor={selected ? 'accent' : 'textSecondary'}
      >
        {label}
      </ThemedText>
    </Pressable>
  );
}
export function ArtifactEditor({
  edit,
  languages,
  disabled,
  onChange,
}: {
  edit: Extract<WorkEdit, { kind: 'artifact' }>;
  languages: string[];
  disabled: boolean;
  onChange: (edit: WorkEdit) => void;
}) {
  const theme = useTheme();
  return (
    <View style={styles.group}>
      {languages.length > 1 ? (
        <View
          accessibilityRole="radiogroup"
          accessibilityLabel="Artifact notation"
          style={styles.choices}
        >
          {languages.map((language) => (
            <Choice
              key={language}
              label={language === 'text' ? 'Text' : language.toUpperCase()}
              selected={edit.language === language}
              disabled={disabled}
              onPress={() => onChange({ ...edit, language })}
            />
          ))}
        </View>
      ) : null}
      <TextInput
        accessibilityLabel="Artifact text"
        multiline
        autoCapitalize="none"
        autoCorrect={false}
        spellCheck={false}
        smartInsertDelete={false}
        editable={!disabled}
        value={edit.body}
        maxLength={ARTIFACT_LIMIT}
        onChangeText={(body) => onChange({ ...edit, body })}
        placeholder="Write your proposal…"
        placeholderTextColor={theme.textSecondary}
        style={[
          styles.code,
          { color: theme.text, backgroundColor: theme.backgroundElement },
        ]}
      />
      <ThemedText type="small" themeColor="textSecondary">
        {new TextEncoder()
          .encode(edit.body.replace(/\r\n?/g, '\n'))
          .length.toLocaleString()}{' '}
        / 65,536 bytes · {edit.language}
      </ThemedText>
      <NativeAction secondary label="Done typing" onPress={Keyboard.dismiss} />
    </View>
  );
}
export function BriefEditor({
  edit,
  disabled,
  onChange,
}: {
  edit: Extract<WorkEdit, { kind: 'brief' }>;
  disabled: boolean;
  onChange: (edit: WorkEdit) => void;
}) {
  const theme = useTheme();
  const [selected, setSelected] = useState<string | null>(null);
  const entry = edit.entries.find((e) => e.id === selected);
  const change = (patch: Partial<BriefEntry>) => {
    if (entry)
      onChange({
        ...edit,
        entries: edit.entries.map((e) =>
          e.id === entry.id ? { ...e, ...patch } : e,
        ),
      });
  };
  if (entry)
    return (
      <View style={styles.group}>
        <NativeAction
          secondary
          label="All notes"
          onPress={() => {
            Keyboard.dismiss();
            setSelected(null);
          }}
        />
        <View
          accessibilityRole="radiogroup"
          accessibilityLabel="Note type"
          style={styles.choices}
        >
          {briefTypes.map((type) => (
            <Choice
              key={type}
              label={briefLabels[type]}
              selected={entry.type === type}
              disabled={disabled}
              onPress={() => change({ type })}
            />
          ))}
        </View>
        <TextInput
          accessibilityLabel="Note text"
          multiline
          editable={!disabled}
          value={entry.text}
          maxLength={BRIEF_ENTRY_LIMIT}
          onChangeText={(text) => change({ text })}
          placeholder="Record your reasoning or an open question…"
          placeholderTextColor={theme.textSecondary}
          style={[
            styles.note,
            { color: theme.text, backgroundColor: theme.backgroundElement },
          ]}
        />
        <ThemedText type="small" themeColor="textSecondary">
          {new TextEncoder()
            .encode(entry.text.replace(/\r\n?/g, '\n'))
            .length.toLocaleString()}{' '}
          / 2,048 bytes
        </ThemedText>
        <View style={styles.pin}>
          <ThemedText style={{ flex: 1 }}>Pin this note</ThemedText>
          <Switch
            accessibilityLabel="Pin this note"
            value={entry.pinned}
            disabled={disabled}
            onValueChange={(pinned) => change({ pinned })}
          />
        </View>
        {entry.sources?.length ? (
          <ThemedText type="small" themeColor="textSecondary">
            Saved evidence links are preserved:{' '}
            {entry.sources
              .map((source) =>
                'turn' in source
                  ? `message ${source.turn}`
                  : `${source.artifact_id} v${source.revision}`,
              )
              .join(', ')}
            .
          </ThemedText>
        ) : null}
        <NativeAction
          secondary
          label="Done typing"
          onPress={Keyboard.dismiss}
        />
        <NativeAction
          secondary
          label="Remove this note"
          disabled={disabled}
          onPress={() =>
            Alert.alert(
              'Remove this note from your draft?',
              'The saved notes stay unchanged until you save.',
              [
                { text: 'Cancel', style: 'cancel' },
                {
                  text: 'Remove note',
                  style: 'destructive',
                  onPress: () => {
                    onChange({
                      ...edit,
                      entries: edit.entries.filter((e) => e.id !== entry.id),
                    });
                    setSelected(null);
                  },
                },
              ],
            )
          }
        />
      </View>
    );
  return (
    <View style={styles.group}>
      <ThemedText themeColor="textSecondary">
        These are your notes, separate from the exercise’s requirements.
      </ThemedText>
      {edit.entries.map((item, index) => (
        <Pressable
          key={item.id}
          accessibilityRole="button"
          disabled={disabled}
          accessibilityLabel={`Edit ${briefLabels[item.type].toLowerCase()} ${index + 1}: ${item.text || 'Empty note'}`}
          onPress={() => setSelected(item.id)}
          style={[styles.noteRow, { backgroundColor: theme.backgroundElement }]}
        >
          <ThemedText type="smallBold">
            {briefLabels[item.type]}
            {item.pinned ? ' · Pinned' : ''}
          </ThemedText>
          <ThemedText numberOfLines={3}>
            {item.text || 'Write this note…'}
          </ThemedText>
        </Pressable>
      ))}
      {!edit.entries.length ? (
        <ThemedText>
          No notes yet. Capture an assumption, decision, or question as you
          work.
        </ThemedText>
      ) : null}
      <NativeAction
        secondary
        label="Add a note"
        disabled={disabled || edit.entries.length >= BRIEF_ENTRY_COUNT}
        onPress={() => {
          const id = Crypto.randomUUID();
          onChange({
            ...edit,
            entries: [
              ...edit.entries,
              {
                id,
                type: 'assumption',
                text: '',
                pinned: false,
                basis: 'learner',
                sources: [],
              },
            ],
          });
          setSelected(id);
        }}
      />
      <ThemedText type="small" themeColor="textSecondary">
        {edit.entries.length} of 50 notes · Save notes to share them with the
        interviewer.
      </ThemedText>
    </View>
  );
}
export function SavedWorkComparison({ edit }: { edit: WorkEdit }) {
  return (
    <Card>
      <SectionHeading>Current saved version</SectionHeading>
      <ThemedText type="small" themeColor="textSecondary">
        Revision {edit.base_revision}
      </ThemedText>
      {edit.kind === 'artifact' ? (
        <LearningText text={edit.body || '(Empty artifact)'} code />
      ) : edit.entries.length ? (
        edit.entries.map((entry) => (
          <View key={entry.id} style={styles.group}>
            <ThemedText type="smallBold">
              {briefLabels[entry.type]}
              {entry.pinned ? ' · Pinned' : ''}
            </ThemedText>
            <LearningText text={entry.text} />
          </View>
        ))
      ) : (
        <ThemedText>No saved notes.</ThemedText>
      )}
    </Card>
  );
}
const styles = StyleSheet.create({
  group: { gap: 12 },
  choices: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  choice: {
    minHeight: 48,
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderRadius: 12,
    justifyContent: 'center',
  },
  code: {
    minHeight: 280,
    maxHeight: 480,
    borderRadius: 12,
    padding: 14,
    textAlignVertical: 'top',
    fontSize: 16,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  note: {
    minHeight: 170,
    maxHeight: 340,
    padding: 14,
    borderRadius: 12,
    textAlignVertical: 'top',
    fontSize: 17,
  },
  noteRow: { gap: 8, padding: 16, borderRadius: 12, minHeight: 64 },
  pin: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
  },
});
