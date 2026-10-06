/** Shared request and draft logic, independent of native modules for regression tests. */
export interface Gift {
  id: number;
  title: string;
  body: string;
  image_url: string | null;
  timestamp: string | null;
  user_id: number;
}

export interface GiftImageInput {
  uri: string;
  name: string;
  type: string;
  /** Expo 57 fetch requires Blob bytes or an Expo File on every platform. */
  file: Blob;
}

export interface GiftInput {
  title: string;
  body: string;
  image?: GiftImageInput | null;
  removeImage?: boolean;
}

export type PhotoDraft = { kind: 'keep' } | { kind: 'replace'; image: GiftImageInput } | { kind: 'remove' };
export const MAX_PHOTO_BYTES = 5 * 1024 * 1024;
export const textLength = (text: string) => Array.from(text.trim()).length;
export const validGiftId = (id: number) => Number.isSafeInteger(id) && id > 0;

export function giftValidation(title: string, body: string): string | null {
  if (!title.trim() || !body.trim()) return 'Enter a title and description.';
  if (textLength(title) > 140 || textLength(body) > 140)
    return 'Title and description must each be 140 characters or fewer.';
  return null;
}

export function photoPreview(photo: PhotoDraft, existing: string | null): string | null {
  return photo.kind === 'replace' ? photo.image.uri : photo.kind === 'remove' ? null : existing;
}

export function draftInput(title: string, body: string, photo: PhotoDraft): GiftInput {
  return {
    title: title.trim(), body: body.trim(),
    ...(photo.kind === 'replace' ? { image: photo.image } : {}),
    ...(photo.kind === 'remove' ? { removeImage: true } : {}),
  };
}

export function giftRequestBody(input: GiftInput): FormData | { title: string; body: string; remove_image?: boolean } {
  if (input.image && input.removeImage) throw new Error('A photo cannot be replaced and removed together.');
  if (!input.image) return {
    title: input.title, body: input.body,
    ...(input.removeImage !== undefined ? { remove_image: input.removeImage } : {}),
  };
  const form = new FormData();
  form.append('title', input.title);
  form.append('body', input.body);
  form.append('image', input.image.file, input.image.name);
  return form;
}

function addedTime(gift: Gift) {
  const time = gift.timestamp ? Date.parse(gift.timestamp) : NaN;
  return Number.isFinite(time) ? time : -Infinity;
}

export function browseGifts(gifts: Gift[], search: string): Gift[] {
  const needle = search.trim().toLocaleLowerCase();
  return gifts.filter((gift) => `${gift.title}\n${gift.body}`.toLocaleLowerCase().includes(needle))
    .sort((a, b) => {
      const first = addedTime(a), second = addedTime(b);
      return first === second ? b.id - a.id : first > second ? -1 : 1;
    });
}

export const wishlistKeys = {
  all: ['wishlist'] as const,
  gifts: () => ['wishlist', 'gifts'] as const,
  gift: (id: number) => ['wishlist', 'gift', id] as const,
};
