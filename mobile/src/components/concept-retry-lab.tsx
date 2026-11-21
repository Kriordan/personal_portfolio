import { useState } from 'react';
import { View } from 'react-native';
import { NativeChoice } from './native-choice';
import { Card, NativeAction } from './screen';
import { ThemedText } from './themed-text';
import { retrySteps, type FailurePoint } from '@/lib/retry-simulation';
const failures = [
  { value: 'after', label: 'Response lost after commit' },
  { value: 'before', label: 'Crash before commit' },
  { value: 'success', label: 'Success arrives' },
] as const;
export function ConceptRetryLab() {
  const [failure, setFailure] = useState<FailurePoint>('after');
  const [reuse, setReuse] = useState('same');
  const [step, setStep] = useState(0);
  const steps = retrySteps(failure, reuse === 'same');
  return (
    <Card>
      <ThemedText type="subtitle" accessibilityRole="header">
        Trace a retry
      </ThemedText>
      <ThemedText themeColor="textSecondary">
        One operation and one database transaction, within the retention window.
      </ThemedText>
      <NativeChoice
        label="First attempt"
        value={failure}
        options={failures}
        onChange={(value) => {
          setFailure(value);
          setStep(0);
        }}
      />
      <NativeChoice
        label="Retry identity"
        value={reuse}
        options={[
          { value: 'same', label: 'Reuse key A' },
          { value: 'new', label: 'New key B' },
        ]}
        onChange={(value) => {
          setReuse(value);
          setStep(0);
        }}
      />
      <View accessibilityLiveRegion="polite" style={{ gap: 8 }}>
        <ThemedText type="smallBold">
          Step {step + 1} of {steps.length}
        </ThemedText>
        <ThemedText>{steps[step].text}</ThemedText>
        <ThemedText type="smallBold">
          Committed orders: {steps[step].orders}
        </ThemedText>
        {steps[step].orders === 2 ? (
          <ThemedText themeColor="danger">
            Changing the key removed the duplicate protection.
          </ThemedText>
        ) : null}
      </View>
      <NativeAction
        label={step === steps.length - 1 ? 'Start again' : 'Next step'}
        onPress={() => setStep((value) => (value + 1) % steps.length)}
      />
    </Card>
  );
}
