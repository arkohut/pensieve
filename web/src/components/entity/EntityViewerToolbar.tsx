import { type ReactNode, useMemo } from 'react';
import { PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen } from 'lucide-react';
import { Button } from '$/components/ui/button';
import { LucideIcon } from '$/components/common/LucideIcon';
import { translateAppName, formatDate, filename } from '$/lib/utils';
import type { Entity } from '$/lib/api/types';

interface Props {
  entity: Entity | null;
  showImage: boolean;
  showDetails: boolean;
  onToggleImage: () => void;
  onToggleDetails: () => void;
  leftAction?: ReactNode;
  rightAction?: ReactNode;
}

function getEntityTitle(doc: Entity): string {
  const aw = doc.metadata_entries?.find((e) => e.key === 'active_window');
  if (aw) return aw.value;
  return doc.filepath ? filename(doc.filepath) : '';
}

function getAppName(doc: Entity): string {
  const aa = doc.metadata_entries?.find((e) => e.key === 'active_app');
  return aa?.value ?? 'unknown';
}

export function EntityViewerToolbar({
  entity,
  showImage,
  showDetails,
  onToggleImage,
  onToggleDetails,
  leftAction,
  rightAction,
}: Props) {
  const displayTitle = entity ? getEntityTitle(entity) : 'unknown';
  const displayAppName = entity ? getAppName(entity) : 'unknown';
  const formattedCreatedAt = useMemo(
    () => (entity?.file_created_at ? formatDate(entity.file_created_at) : ''),
    [entity?.file_created_at],
  );

  // Prevent both panes from being hidden at once: only disable a toggle
  // when clicking it would collapse the last visible pane.
  const imageWouldOrphan = showImage && !showDetails;
  const detailsWouldOrphan = showDetails && !showImage;

  return (
    <div className="relative z-[52] flex w-full items-center gap-2">
      <div className="flex-none">{leftAction}</div>
      <div className="flex min-w-0 flex-1 items-center justify-center">
        <div className="flex min-w-0 items-center gap-2">
          <LucideIcon name={translateAppName(displayAppName) ?? 'Image'} size={20} />
          <p className="truncate text-base font-medium leading-tight">{displayTitle}</p>
          {!showDetails && formattedCreatedAt && (
            <span className="ml-3 font-mono text-xs text-muted-foreground">
              {formattedCreatedAt}
            </span>
          )}
        </div>
      </div>
      <div className="flex flex-none items-center gap-1">
        <Button
          type="button"
          variant="ghost"
          size="icon"
          disabled={imageWouldOrphan}
          className="h-8 w-8 text-muted-foreground hover:text-foreground"
          onClick={onToggleImage}
          aria-label={showImage ? 'Hide image' : 'Show image'}
          title={showImage ? 'Hide image' : 'Show image'}
        >
          {showImage ? <PanelLeftClose size={18} /> : <PanelLeftOpen size={18} />}
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          disabled={detailsWouldOrphan}
          className="h-8 w-8 text-muted-foreground hover:text-foreground"
          onClick={onToggleDetails}
          aria-label={showDetails ? 'Hide details' : 'Show details'}
          title={showDetails ? 'Hide details' : 'Show details'}
        >
          {showDetails ? <PanelRightClose size={18} /> : <PanelRightOpen size={18} />}
        </Button>
        {rightAction}
      </div>
    </div>
  );
}
