import { Button, Host, Label, Menu } from '@expo/ui/swift-ui';
import {
  accessibilityLabel,
  background,
  buttonStyle,
  contentShape,
  disabled,
  frame,
  labelStyle,
  menuIndicator,
  shapes,
  strokeBorder,
  tint,
} from '@expo/ui/swift-ui/modifiers';
import { useTheme } from '@/hooks/use-theme';
import { jobActions, type JobActionsMenuProps } from './job-actions-menu.types';

export function JobActionsMenu(props: JobActionsMenuProps) {
  const theme = useTheme();
  return (
    <Host matchContents ignoreSafeArea="all">
      <Menu
        label={
          <Label title="More job actions" systemImage="ellipsis" modifiers={[
            labelStyle('iconOnly'),
            // Size the label itself: an outer Menu frame only expands layout,
            // leaving the icon as the hit target under SwiftUI's plain style.
            frame({ width: 48, height: 48 }),
            background(theme.backgroundElement, shapes.roundedRectangle({ cornerRadius: 12 })),
            strokeBorder({ content: theme.border, shape: 'roundedRectangle', cornerRadius: 12 }),
            contentShape(shapes.rectangle()),
          ]} />
        }
        modifiers={[
          accessibilityLabel('More job actions'),
          buttonStyle('plain'),
          menuIndicator('hidden'),
          tint(theme.accent),
        ]}
      >
        {jobActions(props).map((action) => (
          <Button
            key={action.id}
            label={action.title}
            systemImage={action.image}
            modifiers={[disabled(!action.enabled)]}
            onPress={() => {
              if (action.enabled) props.onAction(action.id);
            }}
          />
        ))}
      </Menu>
    </Host>
  );
}
