export type JobAction = 'open' | 'copy' | 'edit' | 'archive';

export interface JobActionsMenuProps {
  archived: boolean;
  canOpen: boolean;
  canCopy: boolean;
  canEdit: boolean;
  canArchive: boolean;
  onAction(action: JobAction): void;
}

export function jobActions(props: JobActionsMenuProps) {
  return [
    { id: 'open', title: 'Show listing', image: 'arrow.up.right.square', enabled: props.canOpen },
    { id: 'copy', title: 'Copy link', image: 'doc.on.doc', enabled: props.canCopy },
    { id: 'edit', title: 'Edit job', image: 'pencil', enabled: props.canEdit },
    { id: 'archive', title: props.archived ? 'Restore job' : 'Archive job', image: props.archived ? 'tray.and.arrow.up' : 'archivebox', enabled: props.canArchive },
  ] as const;
}
