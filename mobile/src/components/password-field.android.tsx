import { Text, TextField, type TextFieldProps } from '@expo/ui/jetpack-compose';
import { fillMaxWidth, semantics } from '@expo/ui/jetpack-compose/modifiers';

import type { PasswordFieldProps } from './password-field';

// SDK 57's universal secureTextEntry masks text but does not request a password IME.
export function PasswordField({
  value,
  onChangeText,
  editable,
  onSubmit,
}: PasswordFieldProps) {
  return (
    <TextField
      // Android's useNativeState supplies the native shared object behind the universal type.
      value={value as TextFieldProps['value']}
      onValueChange={onChangeText}
      enabled={editable !== false}
      singleLine
      visualTransformation="password"
      keyboardOptions={{
        keyboardType: 'password',
        capitalization: 'none',
        autoCorrectEnabled: false,
        imeAction: 'go',
      }}
      keyboardActions={{ onGo: onSubmit }}
      modifiers={[fillMaxWidth(), semantics({ contentType: 'password' })]}
    >
      <TextField.Label>
        <Text>Password</Text>
      </TextField.Label>
    </TextField>
  );
}
