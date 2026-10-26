import { View } from 'react-native';
import { ThemedText } from './themed-text';
import { JobFormSection, jobFormStyles as styles } from './job-form-controls';

export function JobHelpContent({
  topic,
}: {
  topic: 'suggestions' | 'capture';
}) {
  return topic === 'suggestions' ? (
    <View style={styles.group}>
      <JobFormSection title="Optional help from the listing">
        <ThemedText>
          Browserless reads the public listing. OpenAI summarizes its text. Your
          notes, profile and screenshots are not sent.
        </ThemedText>
      </JobFormSection>
      <JobFormSection title="You decide what to keep">
        <ThemedText>
          Suggestions can miss or misread details. Use Source to check the
          original wording, especially pay and eligibility restrictions.
        </ThemedText>
        <ThemedText>
          Apply to draft fills the form. Save job keeps your changes. You can
          also enter the job manually.
        </ThemedText>
      </JobFormSection>
    </View>
  ) : (
    <View style={styles.group}>
      <ThemedText>
        Capture sends the public listing URL to Browserless. Avoid private or
        tokenized links. Your job is already saved.
      </ThemedText>
      <ThemedText>
        Public Gem, Greenhouse, Lever, Ashby and Workday listing links are
        supported. Embedded videos are omitted. Check the image against the
        original listing.
      </ThemedText>
    </View>
  );
}
