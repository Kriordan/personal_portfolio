import { Button, Host, Label, Menu } from '@expo/ui/swift-ui';
import { accessibilityLabel, buttonStyle, contentShape, disabled, frame, labelStyle, menuIndicator, shapes, tint } from '@expo/ui/swift-ui/modifiers';
import { useTheme } from '@/hooks/use-theme';
import type { IntervalMenuAction } from './interval-actions';

export function IntervalActions({ actions, label = 'More actions' }: { actions: IntervalMenuAction[]; label?: string }) {
  const theme = useTheme();
  return <Host matchContents ignoreSafeArea="all">
    <Menu label={<Label title={label} systemImage="ellipsis" modifiers={[
      labelStyle('iconOnly'), frame({ width: 48, height: 48 }), contentShape(shapes.rectangle()),
    ]} />} modifiers={[accessibilityLabel(label), buttonStyle('plain'), menuIndicator('hidden'), tint(theme.accent)]}>
      {actions.map((action) => <Button key={action.label} label={action.label}
        modifiers={[disabled(action.disabled ?? false)]} onPress={() => { if (!action.disabled) action.run(); }} />)}
    </Menu>
  </Host>;
}
