import * as ImagePicker from 'expo-image-picker';
import { useState } from 'react';
import { Alert, Image, Pressable, StyleSheet, TextInput, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import type { GiftImageInput, GiftInput } from '@/lib/wishlist-api';

interface GiftFormProps {
  initialTitle?: string;
  initialBody?: string;
  /** Existing remote image, shown until a new local image is picked. */
  existingImageUrl?: string | null;
  submitLabel: string;
  submitting: boolean;
  errorMessage?: string | null;
  onSubmit: (input: GiftInput) => void;
}

function assetToImageInput(asset: ImagePicker.ImagePickerAsset): GiftImageInput {
  return {
    uri: asset.uri,
    name: asset.fileName ?? `gift-${Date.now()}.jpg`,
    type: asset.mimeType ?? 'image/jpeg',
  };
}

export function GiftForm({
  initialTitle = '',
  initialBody = '',
  existingImageUrl = null,
  submitLabel,
  submitting,
  errorMessage,
  onSubmit,
}: GiftFormProps) {
  const theme = useTheme();
  const [title, setTitle] = useState(initialTitle);
  const [body, setBody] = useState(initialBody);
  const [image, setImage] = useState<GiftImageInput | null>(null);

  const previewUri = image?.uri ?? existingImageUrl;
  const canSubmit = title.trim().length > 0 && body.trim().length > 0 && !submitting;

  const pickImage = async () => {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      Alert.alert('Permission required', 'Allow photo library access to attach an image.');
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      allowsEditing: true,
      quality: 0.8,
    });
    if (!result.canceled && result.assets[0]) {
      setImage(assetToImageInput(result.assets[0]));
    }
  };

  return (
    <View style={styles.form}>
      <TextInput
        style={[styles.input, { color: theme.text, backgroundColor: theme.backgroundElement }]}
        placeholder="Title"
        placeholderTextColor={theme.textSecondary}
        value={title}
        onChangeText={setTitle}
        editable={!submitting}
      />
      <TextInput
        style={[
          styles.input,
          styles.multiline,
          { color: theme.text, backgroundColor: theme.backgroundElement },
        ]}
        placeholder="Description"
        placeholderTextColor={theme.textSecondary}
        value={body}
        onChangeText={setBody}
        multiline
        editable={!submitting}
      />

      {previewUri ? (
        <Image source={{ uri: previewUri }} style={styles.preview} resizeMode="cover" />
      ) : null}

      <View style={styles.imageRow}>
        <Pressable
          style={[styles.buttonSecondary, { backgroundColor: theme.backgroundElement }]}
          disabled={submitting}
          onPress={pickImage}
        >
          <ThemedText type="smallBold">
            {previewUri ? 'Change Image' : 'Add Image (optional)'}
          </ThemedText>
        </Pressable>
        {image ? (
          <Pressable
            style={[styles.buttonSecondary, { backgroundColor: theme.backgroundElement }]}
            disabled={submitting}
            onPress={() => setImage(null)}
          >
            <ThemedText type="smallBold">Remove</ThemedText>
          </Pressable>
        ) : null}
      </View>

      <Pressable
        style={[styles.button, !canSubmit && styles.buttonDisabled]}
        disabled={!canSubmit}
        onPress={() => onSubmit({ title: title.trim(), body: body.trim(), image })}
      >
        <ThemedText type="smallBold" style={styles.buttonText}>
          {submitting ? 'Saving…' : submitLabel}
        </ThemedText>
      </Pressable>

      {errorMessage ? (
        <ThemedText type="small" style={styles.error}>
          {errorMessage}
        </ThemedText>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  form: {
    gap: Spacing.two,
  },
  input: {
    borderRadius: Spacing.two,
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.two,
    fontSize: 16,
  },
  multiline: {
    minHeight: 96,
    textAlignVertical: 'top',
  },
  preview: {
    width: '100%',
    height: 200,
    borderRadius: Spacing.two,
  },
  imageRow: {
    flexDirection: 'row',
    gap: Spacing.two,
  },
  button: {
    backgroundColor: '#3c87f7',
    borderRadius: Spacing.two,
    paddingVertical: Spacing.three,
    paddingHorizontal: Spacing.three,
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonSecondary: {
    borderRadius: Spacing.two,
    paddingVertical: Spacing.two,
    paddingHorizontal: Spacing.three,
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonDisabled: {
    opacity: 0.5,
  },
  buttonText: {
    color: '#ffffff',
  },
  error: {
    color: '#d64545',
  },
});
