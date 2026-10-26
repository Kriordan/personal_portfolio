import { useEffect, useRef, useState } from 'react';
import { View } from 'react-native';
import { SourceLink } from './source-link';
import { ThemedText } from './themed-text';
import { InlineError, NativeAction } from './screen';
import {
  JobChoice,
  JobFormField,
  JobFormSection,
  JobTextAction,
  jobFormStyles as styles,
} from './job-form-controls';
import { useNativeText } from '@/hooks/use-native-text';
import {
  reviewSelectionError,
  reviewFieldSelected,
  type ReviewFieldChoice,
  type Extraction,
  type ReviewedDetails,
  type SuggestedBullet,
  type SuggestedField,
} from '@/lib/job-extraction-model';
import type { JobInput } from '@/lib/jobwizard-model';

export function ExtractionReview({
  extraction,
  current,
  currentSummary,
  disabled,
  onUse,
}: {
  extraction: Extraction;
  current: JobInput;
  currentSummary: { text: string }[];
  disabled: boolean;
  onUse(
    fields: Partial<JobInput>,
    details: ReviewedDetails | undefined,
    compared: JobInput,
  ): string | null;
}) {
  const title = useNativeText(extraction.fields.title?.value ?? ''),
    company = useNativeText(extraction.fields.company_name?.value ?? '');
  const [titleChoice, setTitleChoice] = useState<ReviewFieldChoice | null>(
      null,
    ),
    [companyChoice, setCompanyChoice] = useState<ReviewFieldChoice | null>(
      null,
    );
  const useTitle = reviewFieldSelected(titleChoice, current.title),
    useCompany = reviewFieldSelected(companyChoice, current.company_name),
    hasSummary = currentSummary.length > 0;
  const [summaryChoice, setSummaryChoice] = useState<boolean | null>(null),
    [excluded, setExcluded] = useState<number[]>([]),
    [showCurrent, setShowCurrent] = useState(false),
    [showPreview, setShowPreview] = useState(false),
    [error, setError] = useState<string | null>(null);
  const useSummary = summaryChoice ?? !hasSummary;
  const readers = useRef(new Map<number, () => string>());
  const bullets = extraction.result?.bullets ?? [];
  const selectedCount =
    bullets.length - excluded.filter((index) => index < bullets.length).length;
  const apply = () => {
    if (disabled) return;
    const fields: Partial<JobInput> = {};
    if (useTitle && extraction.fields.title) fields.title = title.read().trim();
    if (useCompany && extraction.fields.company_name)
      fields.company_name = company.read().trim();
    const selected = bullets.flatMap((bullet, index) =>
      excluded.includes(index)
        ? []
        : [
            {
              index,
              text: (readers.current.get(index)?.() ?? bullet.text).trim(),
            },
          ],
    );
    const problem = reviewSelectionError(
      fields,
      useSummary ? selected : undefined,
      hasSummary,
    );
    if (problem) {
      setError(problem);
      return;
    }
    setError(
      onUse(
        fields,
        useSummary && selected.length
          ? { extraction_id: extraction.id, bullets: selected }
          : undefined,
        current,
      ),
    );
  };
  return (
    <View style={{ gap: 24 }}>
      {extraction.warnings.length ||
      extraction.result?.more_details ||
      extraction.result?.has_conflicts ? (
        <ThemedText accessibilityLiveRegion="polite">
          {extraction.result?.has_conflicts
            ? 'The listing has conflicting details. Check the source before using them.'
            : 'Some details may be missing. Check the listing for pay and eligibility restrictions.'}
        </ThemedText>
      ) : null}
      <FieldReview
        label="Job title"
        current={current.title}
        suggestion={extraction.fields.title}
        text={title}
        selected={useTitle}
        onSelect={(selected) =>
          setTitleChoice({ selected, compared: current.title })
        }
        disabled={disabled}
      />
      <FieldReview
        label="Company"
        current={current.company_name}
        suggestion={extraction.fields.company_name}
        text={company}
        selected={useCompany}
        onSelect={(selected) =>
          setCompanyChoice({ selected, compared: current.company_name })
        }
        disabled={disabled}
      />
      <JobFormSection title="Important details">
        {hasSummary ? (
          <>
            <JobChoice
              label="Keep current details"
              value={`${currentSummary.length} details`}
              selected={!useSummary}
              disabled={disabled}
              onPress={() => setSummaryChoice(false)}
            />
            {bullets.length ? (
              <JobChoice
                label="Replace with suggestions"
                value={`${bullets.length} suggested details`}
                selected={useSummary}
                disabled={disabled}
                onPress={() => setSummaryChoice(true)}
              />
            ) : null}
            <View style={styles.row}>
              <JobTextAction
                label={
                  showCurrent ? 'Hide current details' : 'View current details'
                }
                expanded={showCurrent}
                onPress={() => setShowCurrent(!showCurrent)}
              />
              {!useSummary && bullets.length ? (
                <JobTextAction
                  label={showPreview ? 'Hide suggestions' : 'View suggestions'}
                  expanded={showPreview}
                  onPress={() => setShowPreview(!showPreview)}
                />
              ) : null}
            </View>
            {showCurrent
              ? currentSummary.map((bullet, index) => (
                  <ThemedText
                    key={index}
                    selectable
                  >{`• ${bullet.text}`}</ThemedText>
                ))
              : null}
          </>
        ) : null}
        {!bullets.length ? (
          <ThemedText themeColor="textSecondary">
            No suggested details are available. You can still use the title and
            company.
          </ThemedText>
        ) : null}
        {useSummary && bullets.length ? (
          <ThemedText
            type="small"
            themeColor="textSecondary"
            accessibilityLiveRegion="polite"
          >{`${selectedCount} of ${bullets.length} selected`}</ThemedText>
        ) : null}
        {/* Keep native text state mounted while the reviewer inspects help/current details. */}
        <View
          style={[styles.group, !useSummary && !showPreview && styles.hidden]}
        >
          {bullets.map((bullet, index) => (
            <BulletReview
              key={`${extraction.id}:${index}`}
              bullet={bullet}
              index={index}
              selected={!excluded.includes(index)}
              choosing={useSummary}
              disabled={disabled}
              register={(reader) => {
                readers.current.set(index, reader);
              }}
              onToggle={() =>
                setExcluded((value) =>
                  value.includes(index)
                    ? value.filter((i) => i !== index)
                    : [...value, index],
                )
              }
            />
          ))}
        </View>
      </JobFormSection>
      {error ? <InlineError message={error} /> : null}
      <View style={styles.compact}>
        <ThemedText type="small" themeColor="textSecondary">
          Applies to your draft. Save the job afterward.
        </ThemedText>
        <NativeAction
          label="Apply to draft"
          disabled={disabled}
          onPress={apply}
        />
      </View>
    </View>
  );
}

function FieldReview({
  label,
  current,
  suggestion,
  text,
  selected,
  disabled,
  onSelect,
}: {
  label: string;
  current: string;
  suggestion: SuggestedField | null | undefined;
  text: ReturnType<typeof useNativeText>;
  selected: boolean;
  disabled: boolean;
  onSelect(value: boolean): void;
}) {
  const [editing, setEditing] = useState(false),
    [source, setSource] = useState(false);
  const identical = current.trim() === text.text.trim();
  return (
    <JobFormSection title={label}>
      {!suggestion ? (
        <ThemedText>{`${label} wasn’t found. ${current.trim() ? 'Your value will be kept.' : 'Enter it in the job form.'}`}</ThemedText>
      ) : (
        <>
          {identical ? (
            <View style={styles.compact}>
              <ThemedText>{current}</ThemedText>
              <ThemedText type="small" themeColor="textSecondary">
                Matches your draft
              </ThemedText>
            </View>
          ) : (
            <View style={styles.group}>
              {current.trim() ? (
                <JobChoice
                  label="Keep mine"
                  value={current}
                  selected={!selected}
                  disabled={disabled}
                  onPress={() => onSelect(false)}
                />
              ) : null}
              <JobChoice
                label="Use listing"
                value={text.text}
                multiple={!current.trim()}
                selected={selected}
                disabled={disabled}
                onPress={() => onSelect(current.trim() ? true : !selected)}
              />
            </View>
          )}
          <View style={styles.row}>
            <SourceLink
              detail={label.toLowerCase()}
              expanded={source}
              onPress={() => setSource(!source)}
            />
            <JobTextAction
              label={editing ? 'Done editing' : 'Edit suggestion'}
              accessibilityLabel={`${editing ? 'Done editing' : 'Edit suggested'} ${label.toLowerCase()}`}
              disabled={disabled}
              onPress={() => {
                text.set(text.read());
                setEditing(!editing);
              }}
            />
          </View>
          {source
            ? suggestion.evidence.map((item) => (
                <ThemedText key={item.block_id} selectable type="small">
                  {item.quote}
                </ThemedText>
              ))
            : null}
          {editing ? (
            <JobFormField
              label={`Suggested ${label.toLowerCase()}`}
              {...text.input}
              editable={!disabled}
            />
          ) : null}
          {text.text !== suggestion.value ? (
            <ThemedText type="small" themeColor="textSecondary">
              Edited by you · source supports the original suggestion
            </ThemedText>
          ) : null}
        </>
      )}
    </JobFormSection>
  );
}

function BulletReview({
  bullet,
  index,
  selected,
  choosing,
  disabled,
  register,
  onToggle,
}: {
  bullet: SuggestedBullet;
  index: number;
  selected: boolean;
  choosing: boolean;
  disabled: boolean;
  register(reader: () => string): void;
  onToggle(): void;
}) {
  const text = useNativeText(bullet.text),
    [editing, setEditing] = useState(false),
    [source, setSource] = useState(false);
  useEffect(() => {
    register(text.read);
  });
  return (
    <View style={styles.compact}>
      {choosing ? (
        <JobChoice
          label={text.text}
          selected={selected}
          multiple
          disabled={disabled}
          onPress={onToggle}
        />
      ) : (
        <ThemedText>{`• ${text.text}`}</ThemedText>
      )}
      <View style={styles.row}>
        <SourceLink
          detail={index + 1}
          expanded={source}
          onPress={() => setSource(!source)}
        />
        {choosing ? (
          <JobTextAction
            label={editing ? 'Done editing' : 'Edit'}
            accessibilityLabel={`${editing ? 'Done editing' : 'Edit'} detail ${index + 1}`}
            disabled={disabled}
            onPress={() => {
              text.set(text.read());
              setEditing(!editing);
            }}
          />
        ) : null}
      </View>
      {editing && choosing ? (
        <JobFormField
          label={`Detail ${index + 1}`}
          {...text.input}
          editable={!disabled}
          multiline
        />
      ) : null}
      {text.text !== bullet.text ? (
        <ThemedText type="small" themeColor="textSecondary">
          Edited by you · source supports the original suggestion
        </ThemedText>
      ) : null}
      {source
        ? bullet.evidence.map((item) => (
            <ThemedText key={item.block_id} selectable type="small">
              {item.quote}
            </ThemedText>
          ))
        : null}
    </View>
  );
}
