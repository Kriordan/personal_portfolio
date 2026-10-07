import { useRouter } from 'expo-router';

import { GiftForm } from '@/components/gift-form';

export default function NewGiftScreen() {
  const router = useRouter();
  return <GiftForm onSaved={(gift) => router.replace(`/wishlist/${gift.id}`)} onClose={() => router.canGoBack() ? router.back() : router.replace('/wishlist')} />;
}
