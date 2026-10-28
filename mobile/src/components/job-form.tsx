import { Stack, useNavigation } from 'expo-router';
import { usePreventRemove } from 'expo-router/react-navigation';
import { useEffect, useRef, useState } from 'react';
import {
  AccessibilityInfo,
  Keyboard,
  KeyboardAvoidingView,
  Modal,
  Platform,
  ScrollView,
  StyleSheet,
  useWindowDimensions,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Card, InlineError, ScreenState } from './screen';
import {
  JobFormField,
  JobInfoButton,
  JobTextAction,
  jobFormStyles as styles,
} from './job-form-controls';
import { JobHelpContent } from './job-help-content';
import { JobImportantDetails } from './job-important-details';
import { ThemedText } from './themed-text';
import { ExtractionReview } from './job-extraction-review';
import { useJobExtraction } from '@/hooks/use-job-extraction';
import {
  extractionMatches,
  extractionErrorForDraft,
  reviewedDetailsError,
  type ReviewedDetails,
  type Extraction,
} from '@/lib/job-extraction-model';
import { JobActivityStatus } from './jobwizard-content';
import { useJobActivity } from '@/hooks/use-jobwizard';
import { useNativeText } from '@/hooks/use-native-text';
import { useTheme } from '@/hooks/use-theme';
import { useAuth } from '@/lib/auth-context';
import { confirmAction } from '@/lib/confirm-action';
import {
  jobwizardApi,
  jobValidation,
  safeJobUrl,
  type Job,
  type JobInput,
} from '@/lib/jobwizard-api';

type JobFormProps = {
  job?: Job;
  onSaved(job: Job): void;
  onClose(): void;
};

export function JobForm(props: JobFormProps) {
  const activity = useJobActivity();
  if (!activity.ready)
    return (
      <ScreenState
        loading={!activity.error}
        title={activity.error ?? 'Checking saved operation'}
        onRetry={
          activity.error ? () => void activity.session.restore() : undefined
        }
      />
    );
  return <ReadyJobForm {...props} activity={activity} />;
}

function ReadyJobForm({
  job,
  onSaved,
  onClose,
  activity,
}: JobFormProps & {
  activity: ReturnType<typeof useJobActivity>;
}) {
  const extraction = useJobExtraction();
  const restoring =
    activity.attempt?.kind === 'save' &&
    activity.attempt.jobId === (job?.id ?? null) &&
    activity.attempt.input.title !== undefined
      ? activity.attempt
      : null;
  const [initial] = useState<JobInput>(() =>
    restoring
      ? (restoring.input as JobInput)
      : (job ?? { title: '', company_name: '', listing_url: '' }),
  );
  const title = useNativeText(initial.title),
    company = useNativeText(initial.company_name),
    url = useNativeText(initial.listing_url);
  const [review, setReview] = useState<{
    details: ReviewedDetails;
    url: string;
    revision?: number;
  } | null>(() =>
    restoring?.input.reviewed_details
      ? {
          details: restoring.input.reviewed_details,
          url: restoring.input.listing_url!,
          revision: restoring.input.expected_revision,
        }
      : null,
  );
  const [usedId, setUsedId] = useState<string | null>(null);
  const [revision, setRevision] = useState(job?.revision),
    [latest, setLatest] = useState<Job | null>(null),
    [error, setError] = useState<string | null>(null);
  const [finished, setFinished] = useState<Job | 'close' | null>(null),
    [sheetVersion, setSheetVersion] = useState(0);
  const [page, setPage] = useState<'form' | 'review' | 'help' | 'details'>(
    'form',
  );
  const helpReturn = useRef<'form' | 'review'>('form');
  const formScroll = useRef<ScrollView>(null);
  const [reviewContext, setReviewContext] = useState<{
    extraction: Extraction;
    current: JobInput;
    summary: { text: string }[];
  } | null>(null);
  const navigate = (next: typeof page) => {
    Keyboard.dismiss();
    setPage(next);
    AccessibilityInfo.announceForAccessibility(
      next === 'review'
        ? 'Review suggestions'
        : next === 'help'
          ? 'About suggestions'
          : next === 'details'
            ? 'Important details'
            : job
              ? 'Edit job'
              : 'Add job',
    );
  };
  const ownRequest = useRef<string | null>(restoring?.input.request_id ?? null),
    submitting = useRef(false),
    notified = useRef(false),
    mounted = useRef(true);
  const navigation = useNavigation(),
    theme = useTheme(),
    { isAuthenticated } = useAuth();
  const { fontScale, width } = useWindowDimensions();
  const stackedToolbar = fontScale > 1.35 || width < 360;
  const busy = !!activity.attempt || !activity.ready;
  const suggestionError = extractionErrorForDraft(extraction, url.text, job?.id ?? null);
  const input = () => ({
    title: title.read().trim(),
    company_name: company.read().trim(),
    listing_url: url.read().trim(),
  });
  const reviewing =
    !!extraction.result &&
    extraction.result.status !== 'accepted' &&
    usedId !== extraction.result.id &&
    extractionMatches(extraction.result, url.text, job?.id ?? null, revision);
  const dirty =
    title.text !== initial.title ||
    company.text !== initial.company_name ||
    url.text !== initial.listing_url ||
    !!review ||
    reviewing;
  const changed = () =>
    title.read() !== initial.title ||
    company.read() !== initial.company_name ||
    url.read() !== initial.listing_url ||
    !!review ||
    reviewing;
  const close = (nativeDismissal = false) => {
    if (submitting.current || activity.phase === 'saving') return;
    if (changed())
      confirmAction(
        'Discard draft?',
        'Your unsaved text will be lost. An operation already sent to the server will still be tracked.',
        'Discard',
        () => setFinished('close'),
        job && nativeDismissal
          ? () => setSheetVersion((v) => v + 1)
          : undefined,
      );
    else setFinished('close');
  };
  const back = () => {
    if (page === 'form') close();
    else navigate(page === 'help' ? helpReturn.current : 'form');
  };
  usePreventRemove(isAuthenticated === true && !finished, ({ data }) => {
    if (submitting.current || activity.phase === 'saving') return;
    if (page !== 'form') {
      back();
      return;
    }
    if (changed())
      confirmAction(
        'Discard draft?',
        'Your unsaved text will be lost. Any pending operation remains tracked.',
        'Discard',
        () => navigation.dispatch(data.action),
      );
    else navigation.dispatch(data.action);
  });
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  useEffect(() => {
    const confirmed = activity.confirmed;
    if (
      confirmed &&
      confirmed.operation.input.request_id === ownRequest.current &&
      'job' in confirmed.result
    )
      setFinished(confirmed.result.job);
  }, [activity.confirmed]);
  useEffect(() => {
    if (finished && !notified.current) {
      notified.current = true;
      if (finished === 'close') onClose();
      else onSaved(finished);
    }
  }, [finished, onClose, onSaved]);
  useEffect(() => {
    if (Platform.OS !== 'web' || (!dirty && !busy) || finished) return;
    const prevent = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', prevent);
    return () => window.removeEventListener('beforeunload', prevent);
  }, [dirty, busy, finished]);
  const save = async () => {
    if (submitting.current || busy) return;
    Keyboard.dismiss();
    const values = input(),
      problem = jobValidation(values, job);
    if (problem) {
      setError(problem);
      formScroll.current?.scrollTo({ y: 0, animated: true });
      return;
    }
    submitting.current = true;
    setError(null);
    const reviewError = review
      ? reviewedDetailsError(review, values.listing_url, revision)
      : null;
    if (reviewError) {
      setError(reviewError);
      formScroll.current?.scrollTo({ y: 0, animated: true });
      submitting.current = false;
      return;
    }
    const pending = activity.session.begin({
      kind: 'save',
      jobId: job?.id ?? null,
      input: {
        ...values,
        ...(review ? { reviewed_details: review.details } : {}),
        ...(job ? { expected_revision: revision } : {}),
      },
    });
    ownRequest.current =
      activity.session.snapshot().attempt?.input.request_id ?? null;
    await pending;
    submitting.current = false;
  };
  const compare = async () => {
    if (!job) return;
    try {
      const result = await jobwizardApi.getJob(job.id);
      if (mounted.current) setLatest(result.job);
    } catch {
      if (mounted.current)
        setError('Couldn’t load the latest job. Your draft is unchanged.');
    }
  };
  const matches =
    !!extraction.result &&
    extractionMatches(extraction.result, url.text, job?.id ?? null, revision);
  const invalidListingUrl = !!url.text.trim() && !safeJobUrl(url.text.trim());
  const canReview =
    reviewing &&
    extraction.result?.status !== 'running' &&
    !!(
      extraction.result?.fields.title ||
      extraction.result?.fields.company_name ||
      extraction.result?.result?.bullets.length
    );
  const canContinue = matches && extraction.result?.can_summarize;
  const retryable =
    matches && ['failed', 'interrupted'].includes(extraction.result!.status);
  const currentDetails =
    review?.details.bullets ?? job?.accepted_details?.bullets ?? [];
  const reviewProblem = review
    ? reviewedDetailsError(review, url.text, revision)
    : null;
  const showHelp = () => {
    helpReturn.current = page === 'review' ? 'review' : 'form';
    navigate('help');
  };
  const openReview = () => {
    const result = extraction.result;
    if (
      !result ||
      !extractionMatches(result, url.read(), job?.id ?? null, revision)
    ) {
      setError('The URL or job version changed. Suggest details again.');
      return;
    }
    // Snapshot live native values, not possibly delayed React change events.
    setReviewContext({
      extraction: result,
      current: {
        title: title.read(),
        company_name: company.read(),
        listing_url: url.read(),
      },
      summary: currentDetails,
    });
    navigate('review');
  };
  const suggest = () => {
    if (busy || !extraction.ready || extraction.working || extraction.uncertain)
      return;
    Keyboard.dismiss();
    const sourceUrl = url.read().trim();
    if (!safeJobUrl(sourceUrl)) {
      // Keep validation in sync with the live native field before any request.
      url.input.onChangeText(sourceUrl);
      return;
    }
    // Native text may be newer than the React event used to render the button.
    const liveMatch =
      !!extraction.result &&
      extractionMatches(
        extraction.result,
        sourceUrl,
        job?.id ?? null,
        revision,
      );
    if (liveMatch && extraction.result?.can_summarize) {
      void extraction.session.continue();
      return;
    }
    setUsedId(null);
    void extraction.session.begin(
      {
        listing_url: sourceUrl,
        ...(liveMatch &&
        ['failed', 'interrupted'].includes(extraction.result!.status)
          ? { retry_of: extraction.result!.id }
          : {}),
        ...(job ? { job_id: job.id, expected_revision: revision } : {}),
      },
      () => mounted.current && url.read().trim() === sourceUrl,
    );
  };
  const applyReview = (
    fields: Partial<JobInput>,
    details: ReviewedDetails | undefined,
    compared: JobInput,
  ) => {
    if (
      !reviewContext ||
      !extractionMatches(
        reviewContext.extraction,
        url.read(),
        job?.id ?? null,
        revision,
      )
    )
      return 'The URL or job version changed. Return to the form and suggest details again.';
    if (
      (fields.title !== undefined && title.read() !== compared.title) ||
      (fields.company_name !== undefined &&
        company.read() !== compared.company_name)
    )
      return 'Your text changed while reviewing. Return to the form and review the current values before replacing them.';
    if (fields.title !== undefined) title.set(fields.title);
    if (fields.company_name !== undefined) company.set(fields.company_name);
    if (details) setReview({ details, url: url.read().trim(), revision });
    setUsedId(reviewContext.extraction.id);
    setError(null);
    navigate('form');
    return null;
  };
  const discardDetails = () => {
    setReview(null);
    setUsedId(null);
    setReviewContext(null);
  };
  const suggestLabel = extraction.working
    ? extraction.stage === 'read'
      ? 'Reading listing…'
      : 'Preparing suggestions…'
    : canContinue
      ? 'Continue preparing details'
      : retryable
        ? extraction.result!.stage === 'summary'
          ? 'Retry summary'
          : 'Read listing again'
        : canReview || usedId
          ? 'Suggest again'
          : 'Suggest details';
  const titleLabel =
    page === 'form'
      ? job
        ? 'Edit job'
        : 'Add job'
      : page === 'review'
        ? 'Review suggestions'
        : page === 'help'
          ? 'About suggestions'
          : 'Important details';
  const content = (
    <SafeAreaView
      edges={['top', 'left', 'right', 'bottom']}
      style={[styles.fill, { backgroundColor: theme.background }]}
    >
      {!job ? <Stack.Screen options={{ headerShown: false }} /> : null}
      <View
        style={[
          localStyles.header,
          { borderBottomColor: theme.backgroundSelected },
        ]}
      >
        <View style={localStyles.toolbar}>
          <JobTextAction
            label={page === 'form' ? 'Cancel' : 'Back'}
            disabled={activity.phase === 'saving'}
            onPress={back}
          />
          {stackedToolbar ? (
            <View style={styles.grow} />
          ) : (
            <ThemedText accessibilityRole="header" style={localStyles.toolbarTitle}>
              {titleLabel}
            </ThemedText>
          )}
          {page === 'form' ? (
            <JobTextAction
              label={activity.phase === 'saving' ? 'Saving…' : 'Save'}
              disabled={busy}
              onPress={() => void save()}
            />
          ) : page === 'review' ? (
            <JobInfoButton label="About suggestions" onPress={showHelp} />
          ) : (
            <View style={localStyles.toolbarSpacer} />
          )}
        </View>
        {stackedToolbar ? (
          <ThemedText accessibilityRole="header" style={localStyles.stackedTitle}>
            {titleLabel}
          </ThemedText>
        ) : null}
      </View>
      <KeyboardAvoidingView
        style={styles.fill}
        behavior={Platform.OS === 'android' ? 'height' : undefined}
      >
        <ScrollView
          ref={formScroll}
          style={page !== 'form' && styles.hidden}
          contentContainerStyle={styles.content}
          keyboardShouldPersistTaps="handled"
          automaticallyAdjustKeyboardInsets
        >
          {error ? <InlineError message={error} /> : null}
          <JobActivityStatus activity={activity} />
          <View style={styles.compact}>
            <JobFormField
              label="Listing URL"
              {...url.input}
              onChangeText={(next) => {
                if (next.trim() !== url.text.trim()) extraction.session.resetFormFeedback();
                url.input.onChangeText(next);
              }}
              editable={!busy}
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="url"
              returnKeyType="done"
            />
            {invalidListingUrl ? (
              <InlineError message="Enter a complete listing link starting with https:// or http://, without spaces." />
            ) : null}
            <View style={styles.spread}>
              <JobTextAction
                label={suggestLabel}
                onPress={suggest}
                disabled={
                  busy ||
                  !extraction.ready ||
                  extraction.working ||
                  extraction.uncertain ||
                  !safeJobUrl(url.text.trim())
                }
              />
              <View style={styles.row}>
                <ThemedText type="small" themeColor="textSecondary">
                  AI suggestions
                </ThemedText>
                <JobInfoButton label="About suggestions" onPress={showHelp} />
              </View>
            </View>
            {extraction.working ? (
              <ThemedText
                type="small"
                themeColor="textSecondary"
                accessibilityLiveRegion="polite"
              >
                {extraction.stage === 'read'
                  ? 'Reading the public listing…'
                  : 'Preparing the bullet summary…'}
              </ThemedText>
            ) : null}
            {suggestionError ? (
              <InlineError message={suggestionError} />
            ) : null}
            {!extraction.ready ? (
              <JobTextAction
                label="Restore suggestion status"
                onPress={() => void extraction.session.restore()}
              />
            ) : null}
            {extraction.request &&
            !url.text.trim() &&
            (extraction.request.job_id ?? null) === (job?.id ?? null) ? (
              <JobTextAction
                label="Use previous listing URL"
                disabled={busy}
                onPress={() => url.set(extraction.request!.listing_url)}
              />
            ) : null}
            <View style={styles.row}>
              {extraction.request &&
              extraction.uncertain &&
              !extraction.working ? (
                <JobTextAction
                  label="Check suggestion status"
                  onPress={() => void extraction.session.check()}
                />
              ) : null}
              {extraction.request &&
              !extraction.result &&
              !extraction.working ? (
                <JobTextAction
                  label="Retry same request"
                  disabled={busy}
                  onPress={() => {
                    const request = extraction.request!;
                    void extraction.session.retrySame(
                      () =>
                        mounted.current &&
                        url.read().trim() === request.listing_url &&
                        (request.job_id ?? null) === (job?.id ?? null) &&
                        request.expected_revision === revision,
                    );
                  }}
                />
              ) : null}
            </View>
            {canReview ? (
              <Card>
                <ThemedText type="smallBold" accessibilityLiveRegion="polite">
                  {extraction.result?.status === 'complete'
                    ? 'Suggestions ready'
                    : 'Some details are ready'}
                </ThemedText>
                <JobTextAction
                  label="Review suggestions"
                  disabled={busy || extraction.working}
                  onPress={openReview}
                />
              </Card>
            ) : null}
            {extraction.result &&
            !matches &&
            !invalidListingUrl &&
            (extraction.result.job_id ?? null) === (job?.id ?? null) &&
            url.text.trim() ? (
              <ThemedText type="small" themeColor="textSecondary">
                Previous suggestions belong to a different URL or job version.
                Your draft is unchanged.
              </ThemedText>
            ) : null}
          </View>
          <JobFormField
            label="Job title"
            {...title.input}
            editable={!busy}
            returnKeyType="next"
          />
          <JobFormField
            label="Company"
            {...company.input}
            editable={!busy}
            returnKeyType="done"
          />
          {currentDetails.length ? (
            <Card>
              <View style={styles.spread}>
                <ThemedText>Important details</ThemedText>
                <JobTextAction
                  label="View details"
                  onPress={() => navigate('details')}
                />
              </View>
              <ThemedText
                type="small"
                themeColor="textSecondary"
              >{`${currentDetails.length} details · ${review ? 'Changes in draft' : 'Saved with this job'}`}</ThemedText>
            </Card>
          ) : null}
          {reviewProblem ? (
            <View style={styles.compact}>
              <InlineError message={reviewProblem} />
              <JobTextAction
                label="Discard selected bullets"
                disabled={busy}
                onPress={discardDetails}
              />
            </View>
          ) : null}
          {job &&
          activity.phase === 'rejected' &&
          activity.attempt?.jobId === job.id ? (
            <JobTextAction
              label="Compare latest version"
              onPress={() => void compare()}
            />
          ) : null}
          {latest ? (
            <Card>
              <ThemedText type="smallBold">Latest saved version</ThemedText>
              <ThemedText>{latest.title}</ThemedText>
              <ThemedText>{latest.company_name}</ThemedText>
              <ThemedText type="small" selectable>
                {latest.listing_url}
              </ThemedText>
              <JobTextAction
                label="Keep my draft with this version"
                disabled={!!activity.attempt && activity.phase !== 'rejected'}
                onPress={() => {
                  void (async () => {
                    if (
                      activity.phase === 'rejected' &&
                      !(await activity.session.clearRejection())
                    )
                      return;
                    setRevision(latest.revision);
                    setLatest(null);
                    setError(
                      (review &&
                        reviewedDetailsError(
                          review,
                          url.read(),
                          latest.revision,
                        )) ||
                        'Your draft is preserved. Review it, then save to update the latest version.',
                    );
                  })();
                }}
              />
            </Card>
          ) : null}
        </ScrollView>
        {reviewContext ? (
          <ScrollView
            style={page !== 'review' && styles.hidden}
            contentContainerStyle={styles.content}
            keyboardShouldPersistTaps="handled"
            automaticallyAdjustKeyboardInsets
          >
            <ExtractionReview
              key={reviewContext.extraction.id}
              extraction={reviewContext.extraction}
              current={reviewContext.current}
              currentSummary={reviewContext.summary}
              disabled={busy || extraction.working}
              onUse={applyReview}
            />
          </ScrollView>
        ) : null}
        {page === 'help' ? (
          <ScrollView contentContainerStyle={styles.content}>
            <JobHelpContent topic="suggestions" />
          </ScrollView>
        ) : null}
        {page === 'details' ? (
          <ScrollView contentContainerStyle={styles.content}>
            {review ? (
              <View style={styles.group}>
                <ThemedText type="small" themeColor="textSecondary">
                  Selected for this draft
                </ThemedText>
                {review.details.bullets.map((bullet) => (
                  <ThemedText
                    key={bullet.index}
                    selectable
                  >{`• ${bullet.text}`}</ThemedText>
                ))}
                {reviewProblem ? <InlineError message={reviewProblem} /> : null}
                {matches &&
                extraction.result?.id === review.details.extraction_id ? (
                  <JobTextAction
                    label="Review choices"
                    disabled={busy}
                    onPress={openReview}
                  />
                ) : null}
                <JobTextAction
                  label="Discard selected bullets"
                  disabled={busy}
                  onPress={() => {
                    discardDetails();
                    navigate('form');
                  }}
                />
              </View>
            ) : (
              <JobImportantDetails details={job?.accepted_details} />
            )}
          </ScrollView>
        ) : null}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
  return job ? (
    <Modal
      key={sheetVersion}
      visible={!finished}
      presentationStyle="pageSheet"
      animationType="slide"
      allowSwipeDismissal={page === 'form' && activity.phase !== 'saving'}
      onRequestClose={() => (page === 'form' ? close(true) : back())}
    >
      {content}
    </Modal>
  ) : (
    content
  );
}
const localStyles = StyleSheet.create({
  header: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  toolbar: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  stackedTitle: { fontWeight: '600', paddingTop: 4 },
  toolbarTitle: { flex: 1, fontWeight: '600', textAlign: 'center' },
  toolbarSpacer: { width: 48 },
});
