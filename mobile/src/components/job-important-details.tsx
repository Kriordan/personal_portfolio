import { useState } from 'react';
import { View } from 'react-native';
import { SourceLink } from './source-link';
import { ThemedText } from './themed-text';
import type { AcceptedDetails } from '@/lib/job-extraction-model';
export function JobImportantDetails({
  details,
}: {
  details?: AcceptedDetails | null;
}) {
  const [opened, setOpened] = useState<number | null>(null);
  if (!details) return null;
  return (
    <View style={{ gap: 14 }}>
      <ThemedText type="subtitle">Important details</ThemedText>
      <ThemedText type="small" themeColor="textSecondary">
        From listing · {new Date(details.fetched_at).toLocaleDateString()}
      </ThemedText>
      {details.outdated ? (
        <ThemedText>
          From an older listing URL. Suggest fresh details to update this
          summary.
        </ThemedText>
      ) : null}
      {details.partial ? (
        <ThemedText>
          This summary may omit important details. Check the original listing.
        </ThemedText>
      ) : null}
      {details.bullets.map((bullet, index) => (
        <View key={index} style={{ gap: 2 }}>
          <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 12 }}>
            <ThemedText selectable style={{ flex: 1 }}>{`• ${bullet.text}`}</ThemedText>
            <SourceLink
              detail={index + 1}
              expanded={opened === index}
              onPress={() => setOpened(opened === index ? null : index)}
            />
          </View>
          {bullet.edited ? (
            <ThemedText type="small" themeColor="textSecondary">
              Edited by you · source supports the original suggestion
            </ThemedText>
          ) : null}
          {opened === index
            ? bullet.evidence.map((evidence) => (
                <ThemedText key={evidence.block_id} selectable type="small">
                  {evidence.quote}
                </ThemedText>
              ))
            : null}
        </View>
      ))}
    </View>
  );
}
