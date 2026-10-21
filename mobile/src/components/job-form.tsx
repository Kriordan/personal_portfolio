import { Button, FieldGroup, Host, RNHostView, Text } from '@expo/ui';
import { useNavigation } from 'expo-router';
import { usePreventRemove } from 'expo-router/react-navigation';
import { useEffect, useRef, useState } from 'react';
import { KeyboardAvoidingView, Modal, Platform, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { NativeField } from './native-form';
import { InlineError, PageHeading, ScreenState } from './screen';
import { JobActivityStatus } from './jobwizard-content';
import { useJobActivity } from '@/hooks/use-jobwizard';
import { useNativeText } from '@/hooks/use-native-text';
import { useTheme } from '@/hooks/use-theme';
import { useAuth } from '@/lib/auth-context';
import { confirmAction } from '@/lib/confirm-action';
import {
  jobwizardApi,
  jobValidation,
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
  const [revision, setRevision] = useState(job?.revision),
    [latest, setLatest] = useState<Job | null>(null),
    [error, setError] = useState<string | null>(null);
  const [finished, setFinished] = useState<Job | 'close' | null>(null),
    [sheetVersion, setSheetVersion] = useState(0),
    [width, setWidth] = useState(320);
  const ownRequest = useRef<string | null>(restoring?.input.request_id ?? null),
    submitting = useRef(false),
    notified = useRef(false),
    mounted = useRef(true);
  const navigation = useNavigation(),
    theme = useTheme(),
    { isAuthenticated } = useAuth();
  const busy = !!activity.attempt || !activity.ready;
  const input = () => ({
    title: title.read().trim(),
    company_name: company.read().trim(),
    listing_url: url.read().trim(),
  });
  const dirty =
    title.text !== initial.title ||
    company.text !== initial.company_name ||
    url.text !== initial.listing_url;
  const changed = () =>
    title.read() !== initial.title ||
    company.read() !== initial.company_name ||
    url.read() !== initial.listing_url;
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
  usePreventRemove(isAuthenticated === true && !finished, ({ data }) => {
    if (submitting.current || activity.phase === 'saving') return;
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
    const values = input(),
      problem = jobValidation(values, job);
    if (problem) {
      setError(problem);
      return;
    }
    submitting.current = true;
    setError(null);
    const pending = activity.session.begin({
      kind: 'save',
      jobId: job?.id ?? null,
      input: { ...values, ...(job ? { expected_revision: revision } : {}) },
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
  const content = (
    <SafeAreaView
      onLayout={(event) => setWidth(event.nativeEvent.layout.width)}
      edges={
        job ? ['top', 'left', 'right', 'bottom'] : ['left', 'right', 'bottom']
      }
      style={{ flex: 1, backgroundColor: theme.background }}
    >
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === 'android' ? 'height' : undefined}
      >
        <Host style={{ flex: 1 }} seedColor={theme.accent}>
          <FieldGroup>
            <FieldGroup.Section>
              <RNHostView matchContents>
                <View style={{ width: Math.max(1, width - 64) }}>
                  <PageHeading
                    title={job ? 'Edit job' : 'Add job'}
                    subtitle="Save the details now. Capture a screenshot afterward if you want one."
                  />
                </View>
              </RNHostView>
              <NativeField
                label="Job title"
                {...title.input}
                editable={!busy}
                returnKeyType="next"
              />
              <NativeField
                label="Company"
                {...company.input}
                editable={!busy}
                returnKeyType="next"
              />
              <NativeField
                label="Listing URL"
                {...url.input}
                editable={!busy}
                autoCapitalize="none"
                autoCorrect={false}
                keyboardType="url"
                returnKeyType="done"
              />
              <Text>Title and company: up to 200 characters each.</Text>
            </FieldGroup.Section>
            <FieldGroup.Section>
              {error ||
              activity.error ||
              activity.attempt ||
              !activity.ready ? (
                <RNHostView matchContents>
                  <View style={{ width: Math.max(1, width - 64) }}>
                    {error ? <InlineError message={error} /> : null}
                    <JobActivityStatus activity={activity} />
                  </View>
                </RNHostView>
              ) : null}
              {job ? (
                <Button
                  label="Compare latest version"
                  variant="text"
                  onPress={() => void compare()}
                  disabled={activity.phase === 'saving'}
                />
              ) : null}
              {latest ? (
                <>
                  <Text>{`Latest saved version: ${latest.title}\n${latest.company_name}\n${latest.listing_url}`}</Text>
                  <Button
                    label="Keep my draft with this version"
                    variant="outlined"
                    disabled={
                      !!activity.attempt && activity.phase !== 'rejected'
                    }
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
                          'Your draft is preserved. Review it, then save to update the latest version.',
                        );
                      })();
                    }}
                  />
                </>
              ) : null}
              <Button
                label={
                  activity.phase === 'saving'
                    ? 'Saving…'
                    : job
                      ? 'Save changes'
                      : 'Save job'
                }
                onPress={() => void save()}
                disabled={busy}
              />
              <Button
                label="Close"
                variant="text"
                onPress={() => close()}
                disabled={activity.phase === 'saving'}
              />
            </FieldGroup.Section>
          </FieldGroup>
        </Host>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
  return job ? (
    <Modal
      key={sheetVersion}
      visible={!finished}
      presentationStyle="pageSheet"
      animationType="slide"
      allowSwipeDismissal={activity.phase !== 'saving'}
      onRequestClose={() => close(true)}
    >
      {content}
    </Modal>
  ) : (
    content
  );
}
