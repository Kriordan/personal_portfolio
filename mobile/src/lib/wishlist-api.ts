import { apiRequest } from '@/lib/api-client';

// Shapes mirror project/api/wishlist.py and wishlist_service.serialize_gift().

export interface Gift {
  id: number;
  title: string;
  body: string;
  image_url: string | null;
  timestamp: string | null;
  user_id: number;
}

/** A local image selected with expo-image-picker, ready for multipart upload. */
export interface GiftImageInput {
  uri: string;
  name: string;
  type: string;
}

export interface GiftInput {
  title: string;
  body: string;
  image?: GiftImageInput | null;
}

/**
 * Build the request body for create/update. Uses multipart FormData when an
 * image is attached (the Flask endpoint reads request.files), plain JSON otherwise.
 */
function giftRequestBody(input: GiftInput): FormData | { title: string; body: string } {
  if (!input.image) {
    return { title: input.title, body: input.body };
  }
  const form = new FormData();
  form.append('title', input.title);
  form.append('body', input.body);
  // React Native FormData accepts { uri, name, type } file descriptors.
  form.append('image', input.image as unknown as Blob);
  return form;
}

export const wishlistApi = {
  getGifts(): Promise<{ gifts: Gift[] }> {
    return apiRequest<{ gifts: Gift[] }>('/wishlist/gifts');
  },

  getGift(giftId: number): Promise<{ gift: Gift }> {
    return apiRequest<{ gift: Gift }>(`/wishlist/gifts/${giftId}`);
  },

  createGift(input: GiftInput): Promise<{ gift: Gift }> {
    return apiRequest<{ gift: Gift }>('/wishlist/gifts', {
      method: 'POST',
      body: giftRequestBody(input),
    });
  },

  updateGift(giftId: number, input: GiftInput): Promise<{ gift: Gift }> {
    return apiRequest<{ gift: Gift }>(`/wishlist/gifts/${giftId}`, {
      method: 'PUT',
      body: giftRequestBody(input),
    });
  },

  deleteGift(giftId: number): Promise<{ message: string }> {
    return apiRequest<{ message: string }>(`/wishlist/gifts/${giftId}`, {
      method: 'DELETE',
    });
  },
};

export const wishlistKeys = {
  all: ['wishlist'] as const,
  gifts: () => ['wishlist', 'gifts'] as const,
  gift: (giftId: number) => ['wishlist', 'gift', giftId] as const,
};
