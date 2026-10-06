import { Alert, Platform } from 'react-native';

export function confirmAction(title: string, message: string, actionLabel: string, onConfirm: () => void, onCancel?: () => void) {
  if (Platform.OS === 'web') {
    if (window.confirm(`${title}\n\n${message}`)) onConfirm();
    else onCancel?.();
    return;
  }
  Alert.alert(title, message, [
    { text: 'Cancel', style: 'cancel', onPress: onCancel },
    { text: actionLabel, style: 'destructive', onPress: onConfirm },
  ], { cancelable: false });
}
