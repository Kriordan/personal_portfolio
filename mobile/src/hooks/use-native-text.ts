import { useNativeState } from '@expo/ui';
import { useState } from 'react';

/** Read native text at submission time; change events can lag behind the visible field. */
export function useNativeText(initialValue = '') {
  const value = useNativeState(initialValue);
  const [text, setText] = useState(initialValue);
  return {
    text,
    input: { value, onChangeText: setText },
    read: () => value.value,
    clear: () => {
      // Expo's observable is mutable native storage, not an immutable React state value.
      // eslint-disable-next-line react-hooks/immutability
      value.value = '';
      setText('');
    },
  };
}
