import { File } from 'expo-file-system';
import { ImageManipulator, SaveFormat } from 'expo-image-manipulator';
import type { ImagePickerAsset } from 'expo-image-picker';
import { Platform } from 'react-native';

import { MAX_PHOTO_BYTES, type GiftImageInput } from './wishlist-model';

/** Normalize to actual JPEG bytes; never infer an encoding from a filename. */
export async function prepareWishlistPhoto(asset: ImagePickerAsset): Promise<GiftImageInput> {
  const context = ImageManipulator.manipulate(asset.uri);
  let rendered;
  try {
    if (Math.max(asset.width, asset.height) > 2048)
      context.resize(asset.width >= asset.height ? { width: 2048 } : { height: 2048 });
    rendered = await context.renderAsync();
    const result = await rendered.saveAsync({ format: SaveFormat.JPEG, compress: 0.8 });
    const file = Platform.OS === 'web' ? await (await fetch(result.uri)).blob() : new File(result.uri);
    const size = file.size;
    if (size > MAX_PHOTO_BYTES) throw new Error('This photo is still larger than 5 MiB. Choose a smaller photo.');
    return { uri: result.uri, name: 'wishlist-photo.jpg', type: 'image/jpeg', file };
  } finally {
    rendered?.release();
    context.release();
  }
}
