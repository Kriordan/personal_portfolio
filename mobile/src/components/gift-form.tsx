import { Button, FieldGroup, Host, RNHostView, Text } from '@expo/ui';
import { usePreventRemove } from 'expo-router/react-navigation';
import { useNavigation } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
import { useEffect, useRef, useState } from 'react';
import { KeyboardAvoidingView, Modal, Platform, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { GiftPhoto } from '@/components/gift-photo';
import { NativeField } from '@/components/native-form';
import { InlineError, PageHeading } from '@/components/screen';
import { useNativeText } from '@/hooks/use-native-text';
import { useTheme } from '@/hooks/use-theme';
import { useWishlistActions } from '@/hooks/use-wishlist';
import { ApiError } from '@/lib/api-client';
import { useAuth } from '@/lib/auth-context';
import { confirmAction } from '@/lib/confirm-action';
import { draftInput, giftValidation, photoPreview, textLength, type Gift, type PhotoDraft } from '@/lib/wishlist-model';
import { prepareWishlistPhoto } from '@/lib/wishlist-photo';

/** Draft state lives above Modal so a cancelled native dismissal cannot erase it. */
export function GiftForm({ gift, onSaved, onClose, onDeleted }: { gift?: Gift; onSaved: (gift: Gift) => void; onClose: () => void; onDeleted?: () => void }) {
  const title = useNativeText(gift?.title ?? '');
  const body = useNativeText(gift?.body ?? '');
  const [photo, setPhoto] = useState<PhotoDraft>({ kind: 'keep' });
  const [error, setError] = useState<string | null>(null);
  const [photoError, setPhotoError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [picking, setPicking] = useState(false);
  const [sheetVersion, setSheetVersion] = useState(0);
  const [formWidth, setFormWidth] = useState(320);
  const [finished, setFinished] = useState<Gift | 'close' | 'deleted' | null>(null);
  const locked = useRef(false);
  const mounted = useRef(true);
  const notified = useRef(false);
  const navigation = useNavigation();
  const theme = useTheme();
  const { isAuthenticated } = useAuth();
  const { create, update, remove } = useWishlistActions();
  const busy = pending || picking;
  const dirty = title.text !== (gift?.title ?? '') || body.text !== (gift?.body ?? '') || photo.kind !== 'keep';
  const hasChanges = () => title.read() !== (gift?.title ?? '') || body.read() !== (gift?.body ?? '') || photo.kind !== 'keep';
  const preview = photoPreview(photo, gift?.image_url ?? null);
  const restoreSheet = () => setSheetVersion((version) => version + 1);
  const askDiscard = (discard: () => void, cancel?: () => void) => confirmAction('Discard changes?', 'Your unsaved text and photo changes will be lost.', 'Discard', discard, cancel);
  const requestClose = (nativeDismissal = false) => {
    if (locked.current) return;
    if (hasChanges()) askDiscard(() => setFinished('close'), gift && nativeDismissal ? restoreSheet : undefined);
    else setFinished('close');
  };

  usePreventRemove(isAuthenticated === true && !finished, ({ data }) => {
    if (locked.current) return;
    if (hasChanges()) askDiscard(() => navigation.dispatch(data.action));
    else navigation.dispatch(data.action);
  });
  useEffect(() => {
    if (!finished || notified.current) return;
    notified.current = true;
    if (finished === 'close') onClose();
    else if (finished === 'deleted') onDeleted?.();
    else onSaved(finished);
  }, [finished, onClose, onSaved, onDeleted]);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);
  useEffect(() => {
    if (Platform.OS !== 'web' || (!dirty && !busy) || finished) return;
    const preventUnload = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', preventUnload);
    return () => window.removeEventListener('beforeunload', preventUnload);
  }, [dirty, busy, finished]);

  const pick = async () => {
    if (locked.current) return;
    locked.current = true;
    setPicking(true);
    setPhotoError(null);
    try {
      // The system's still-photo picker grants access to the selected asset.
      const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], allowsEditing: false, allowsMultipleSelection: false });
      if (!result.canceled && result.assets[0]) {
        const image = await prepareWishlistPhoto(result.assets[0]);
        if (mounted.current) setPhoto({ kind: 'replace', image });
      }
    } catch {
      if (mounted.current) setPhotoError('Couldn’t prepare this photo. Choose a smaller photo or a JPEG/PNG from your library. Your draft is unchanged.');
    } finally {
      locked.current = false;
      if (mounted.current) setPicking(false);
    }
  };
  const submit = async () => {
    if (locked.current) return;
    const currentTitle = title.read(), currentBody = body.read();
    const validation = giftValidation(currentTitle, currentBody);
    if (validation) { setError(validation); return; }
    locked.current = true;
    setPending(true);
    setError(null);
    try {
      const input = draftInput(currentTitle, currentBody, photo);
      const result = gift ? await update.mutateAsync({ id: gift.id, input }) : await create.mutateAsync(input);
      if (mounted.current) setFinished(result.gift);
    } catch (cause) {
      if (mounted.current) setError(cause instanceof Error && cause.name === 'ApiError'
        ? cause instanceof ApiError && cause.status === 404 ? 'This gift is no longer available. Close this draft to return to Wishlist.' : cause.message
        : 'Couldn’t confirm the save. It may have succeeded. Your draft is still here; close it and check Wishlist before trying again.');
    } finally {
      locked.current = false;
      if (mounted.current) setPending(false);
    }
  };
  const deleteGift = () => {
    if (!gift || locked.current) return;
    confirmAction('Delete gift?', `Delete “${gift.title}”? This cannot be undone.`, 'Delete', () => {
      if (locked.current) return;
      locked.current = true;
      setPending(true);
      setDeleting(true);
      setError(null);
      void remove.mutateAsync(gift.id).then(() => {
        if (mounted.current) setFinished('deleted');
      }).catch((cause) => {
        if (mounted.current) setError(cause instanceof Error && cause.name === 'ApiError' ? cause.message : 'Couldn’t confirm deletion. Close the draft and refresh Wishlist before trying again.');
      }).finally(() => {
        locked.current = false;
        if (mounted.current) { setPending(false); setDeleting(false); }
      });
    });
  };

  const content = (
    <SafeAreaView onLayout={(event) => setFormWidth(event.nativeEvent.layout.width)} edges={gift ? ['top', 'left', 'right', 'bottom'] : ['left', 'right', 'bottom']} style={[styles.fill, { backgroundColor: theme.background }]}>
      <KeyboardAvoidingView style={styles.fill} behavior={Platform.OS === 'android' ? 'height' : undefined}>
        <Host style={styles.fill} seedColor={theme.accent}>
          <FieldGroup>
            <FieldGroup.Section>
              <FieldGroup.SectionHeader>
                <RNHostView matchContents>
                  <View style={{ width: Math.max(1, formWidth - 64) }}>
                    <PageHeading title={gift ? 'Edit gift' : 'Save a little inspiration.'} subtitle={gift ? 'Changes take effect when you save.' : 'Add something you’d love to remember.'} />
                  </View>
                </RNHostView>
              </FieldGroup.SectionHeader>
              <NativeField label="Title" {...title.input} editable={!busy} returnKeyType="next" />
              <Text>{`${textLength(title.text)} / 140 characters`}</Text>
              <NativeField label="Description" {...body.input} editable={!busy} multiline />
              <Text>{`${textLength(body.text)} / 140 characters · Required`}</Text>
            </FieldGroup.Section>
            <FieldGroup.Section>
              <RNHostView matchContents><View style={[styles.photo, { width: Math.max(1, formWidth - 64) }]}><GiftPhoto uri={preview} /></View></RNHostView>
              <Button label={picking ? 'Preparing photo…' : preview ? 'Change photo' : 'Choose photo'} onPress={() => void pick()} disabled={busy} variant="outlined" />
              <Text>One library photo, up to 5 MiB. Photos are resized automatically.</Text>
              {preview ? <Button label="Remove photo" variant="text" disabled={busy} onPress={() => { setPhoto(gift?.image_url ? { kind: 'remove' } : { kind: 'keep' }); setPhotoError(null); }} /> : null}
              {photo.kind !== 'keep' && gift?.image_url ? <Button label="Undo photo change" variant="text" disabled={busy} onPress={() => { setPhoto({ kind: 'keep' }); setPhotoError(null); }} /> : null}
              {photo.kind === 'remove' ? <Text>The photo will be removed from this gift when you save.</Text> : null}
              {photoError ? <Text>{photoError}</Text> : null}
            </FieldGroup.Section>
            <FieldGroup.Section>
              {error ? <RNHostView matchContents><View style={{ width: Math.max(1, formWidth - 64) }}><InlineError message={error} /></View></RNHostView> : null}
              <Button label={pending ? deleting ? 'Deleting…' : 'Saving…' : gift ? 'Save changes' : 'Add gift'} onPress={() => void submit()} disabled={busy || !!giftValidation(title.text, body.text)} />
              <Button label="Close" variant="text" onPress={() => requestClose()} disabled={busy} />
              {gift ? <Button label="Delete gift…" variant="text" onPress={deleteGift} disabled={busy} /> : null}
            </FieldGroup.Section>
          </FieldGroup>
        </Host>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
  return gift ? (
    <Modal key={sheetVersion} visible={!finished} presentationStyle="pageSheet" animationType="slide" allowSwipeDismissal={!busy} onRequestClose={() => requestClose(true)}>
      {content}
    </Modal>
  ) : content;
}
const styles = StyleSheet.create({
  fill: { flex: 1 },
  photo: { height: 220, width: '100%' },
});
