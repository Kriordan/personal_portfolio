import type { TextInputProps } from '@expo/ui';

import { NativeField } from '@/components/native-form';

export type PasswordFieldProps = Pick<
  TextInputProps,
  'value' | 'onChangeText' | 'editable'
> & {
  onSubmit: () => void;
};

export function PasswordField({ onSubmit, ...props }: PasswordFieldProps) {
  return (
    <NativeField
      {...props}
      label="Password"
      autoComplete="password"
      secureTextEntry
      autoCapitalize="none"
      autoCorrect={false}
      returnKeyType="go"
      onSubmitEditing={onSubmit}
    />
  );
}
