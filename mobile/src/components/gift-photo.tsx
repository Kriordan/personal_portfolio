import { Image } from 'expo-image';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { useTheme } from '@/hooks/use-theme';

export function GiftPhoto({ uri, thumbnail = false }: { uri: string | null; thumbnail?: boolean }) {
  const theme = useTheme();
  const [failedUri, setFailedUri] = useState<string | null>(null);
  const failed = !!uri && failedUri === uri;
  return (
    <View style={[thumbnail ? styles.thumbnail : styles.photo, { backgroundColor: theme.backgroundSelected }]} accessible={!thumbnail} accessibilityLabel={failed ? 'Photo unavailable' : uri ? 'Gift photo' : 'No photo'}>
      {uri && !failed ? (
        <Image source={{ uri }} recyclingKey={uri} style={styles.image} contentFit={thumbnail ? 'cover' : 'contain'} onError={() => setFailedUri(uri)} accessible={false} />
      ) : (
        <ThemedText type="small" themeColor="textSecondary" accessible={false}>{thumbnail ? '◇' : failed ? 'Photo unavailable' : 'No photo yet'}</ThemedText>
      )}
    </View>
  );
}
const styles = StyleSheet.create({
  thumbnail: { width: 64, height: 64, borderRadius: 12, overflow: 'hidden', alignItems: 'center', justifyContent: 'center' },
  photo: { height: 220, width: '100%', borderRadius: 16, overflow: 'hidden', alignItems: 'center', justifyContent: 'center' },
  image: { width: '100%', height: '100%' },
});
