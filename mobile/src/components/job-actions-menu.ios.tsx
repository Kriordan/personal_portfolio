import { Button, Host, Menu } from '@expo/ui/swift-ui';
import {
  accessibilityLabel,
  disabled,
  frame,
  labelStyle,
  tint,
} from '@expo/ui/swift-ui/modifiers';
import { useTheme } from '@/hooks/use-theme';
import { jobActions, type JobActionsMenuProps } from './job-actions-menu.types';

export function JobActionsMenu(props: JobActionsMenuProps) {
  const theme = useTheme();
  return (
    <Host matchContents ignoreSafeArea="all">
      <Menu
        label="More job actions"
        systemImage="ellipsis"
        modifiers={[
          accessibilityLabel('More job actions'),
          labelStyle('iconOnly'),
          frame({ width: 44, height: 44 }),
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
