import { Button, Column, Text } from '@expo/ui';
import { useEffect, useRef, useState } from 'react';
import { fillWidth } from './native-width';
import { NativeField } from './native-form';
import { useNativeText } from '@/hooks/use-native-text';
import type {
  Extraction,
  ReviewedDetails,
  SuggestedBullet,
} from '@/lib/job-extraction-model';
import type { JobInput } from '@/lib/jobwizard-model';
import { useSuggestedField } from '@/lib/job-extraction-model';

export function ExtractionReview({
  extraction,
  current,
  hasSummary,
  currentSummary,
  disabled,
  onUse,
}: {
  extraction: Extraction;
  current: JobInput;
  hasSummary: boolean;
  currentSummary: { text: string }[];
  disabled: boolean;
  onUse(
    fields: Partial<JobInput>,
    review: ReviewedDetails | undefined,
    compared: JobInput,
  ): void;
}) {
  const title = useNativeText(extraction.fields.title?.value ?? ''),
    company = useNativeText(extraction.fields.company_name?.value ?? '');
  const [titleChoice, setUseTitle] = useState<boolean | null>(null),
    [companyChoice, setUseCompany] = useState<boolean | null>(null);
  const useTitle = useSuggestedField(titleChoice, current.title);
  const useCompany = useSuggestedField(companyChoice, current.company_name);
  const [useSummary, setUseSummary] = useState(!hasSummary),
    [removed, setRemoved] = useState<number[]>([]),
    [error, setError] = useState<string | null>(null);
  const readers = useRef(new Map<number, () => string>());
  const bullets = extraction.result?.bullets ?? [];
  return (
    <Column spacing={20} {...fillWidth}>
      <Column spacing={12} {...fillWidth}>
        <Text>Review suggestions</Text>
        <Text>
          Check every detail against the listing. Suggestions can miss or
          misinterpret information.
        </Text>
        {extraction.warnings.length || extraction.result?.more_details ? (
          <Text>
            Some details are missing, conflicting or too complex for a short
            summary. Check the original listing, including its pay and
            eligibility restrictions.
          </Text>
        ) : null}
        <Text>{`Current title: ${current.title || 'Not entered'}`}</Text>
        {extraction.fields.title ? (
          <>
            <NativeField
              label="Suggested title"
              {...title.input}
              editable={!disabled}
            />
            <Button
              label={
                useTitle ? '✓ Use suggested title' : 'Use suggested title'
              }
              variant="outlined"
              disabled={disabled}
              onPress={() => setUseTitle(!useTitle)}
            />
            <Text>{`Source: ${extraction.fields.title.evidence.map((e) => e.quote).join(' ')}`}</Text>
          </>
        ) : (
          <Text>Title was not found. Enter it manually.</Text>
        )}
        <Text>{`Current company: ${current.company_name || 'Not entered'}`}</Text>
        {extraction.fields.company_name ? (
          <>
            <NativeField
              label="Suggested company"
              {...company.input}
              editable={!disabled}
            />
            <Button
              label={
                useCompany
                  ? '✓ Use suggested company'
                  : 'Use suggested company'
              }
              variant="outlined"
              disabled={disabled}
              onPress={() => setUseCompany(!useCompany)}
            />
            <Text>{`Source: ${extraction.fields.company_name.evidence.map((e) => e.quote).join(' ')}`}</Text>
          </>
        ) : (
          <Text>Company was not verified. Enter it manually.</Text>
        )}
      </Column>
      {bullets.length ? (
        <Column spacing={12} {...fillWidth}>
          <Text>Important details · up to 8 bullets</Text>
          {hasSummary ? (
            <>
              <Text>
                Current details · kept unless you select the new bullets
              </Text>
              {currentSummary.map((bullet, index) => (
                <Text key={`current-${index}`}>{`• ${bullet.text}`}</Text>
              ))}
            </>
          ) : null}
          <Button
            label={useSummary ? '✓ Use new bullets' : 'Use new bullets'}
            variant="outlined"
            disabled={disabled}
            onPress={() => setUseSummary(!useSummary)}
          />
          {bullets.map((bullet, index) =>
            removed.includes(index) ? null : (
              <BulletEditor
                key={`suggested-${index}`}
                index={index}
                bullet={bullet}
                disabled={disabled}
                register={(reader) => {
                  readers.current.set(index, reader);
                }}
                onRemove={() => setRemoved((value) => [...value, index])}
              />
            ),
          )}
        </Column>
      ) : null}
      <Column spacing={12} {...fillWidth}>
        {error ? <Text>{error}</Text> : null}
        <Button
          label="Use selected suggestions"
          disabled={disabled}
          onPress={() => {
            const selected = bullets.flatMap((bullet, index) =>
              removed.includes(index)
                ? []
                : [
                    {
                      index,
                      text: (
                        readers.current.get(index)?.() ?? bullet.text
                      ).trim(),
                    },
                  ],
            );
            if (
              useSummary &&
              selected.some((b) => !b.text || [...b.text].length > 300)
            ) {
              setError(
                'Each bullet needs 1–300 characters. Remove an empty bullet.',
              );
              return;
            }
            const fields: Partial<JobInput> = {};
            if (useTitle && extraction.fields.title)
              fields.title = title.read().trim();
            if (useCompany && extraction.fields.company_name)
              fields.company_name = company.read().trim();
            if (
              Object.values(fields).some(
                (value) => !value || [...value].length > 200,
              )
            ) {
              setError('Title and company need 1–200 characters.');
              return;
            }
            onUse(
              fields,
              useSummary && bullets.length
                ? { extraction_id: extraction.id, bullets: selected }
                : undefined,
              current,
            );
          }}
        />
        <Text>These changes fill your draft. Save job to keep them.</Text>
      </Column>
    </Column>
  );
}
function BulletEditor({
  bullet,
  index,
  disabled,
  register,
  onRemove,
}: {
  bullet: SuggestedBullet;
  index: number;
  disabled: boolean;
  register(reader: () => string): void;
  onRemove(): void;
}) {
  const text = useNativeText(bullet.text),
    [source, setSource] = useState(false);
  useEffect(() => {
    register(text.read);
  });
  return (
    <Column spacing={8} {...fillWidth}>
      <NativeField
        label={`Detail ${index + 1}`}
        {...text.input}
        editable={!disabled}
        multiline
      />
      <Text>
        {text.text === bullet.text
          ? 'Suggested from listing'
          : 'Edited by you · original source below'}
      </Text>
      <Button
        label={source ? 'Hide source' : `View source for detail ${index + 1}`}
        variant="text"
        onPress={() => setSource(!source)}
      />
      {source ? (
        <Text>{bullet.evidence.map((e) => e.quote).join('\n\n')}</Text>
      ) : null}
      <Button
        label={`Remove detail ${index + 1}`}
        variant="text"
        disabled={disabled}
        onPress={onRemove}
      />
    </Column>
  );
}
