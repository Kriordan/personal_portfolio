import { apiRequest } from '@/lib/api-client';

import { giftRequestBody, type Gift, type GiftInput } from './wishlist-model';
export { wishlistKeys } from './wishlist-model';
export type { Gift, GiftInput, GiftImageInput } from './wishlist-model';

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
