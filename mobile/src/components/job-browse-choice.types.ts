import type { NativeChoiceProps } from './native-choice.types';

export interface JobBrowseChoiceProps<T extends string>
  extends Omit<NativeChoiceProps<T>, 'enabled'> {
  icon: 'filter' | 'sort';
}
