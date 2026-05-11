import { type ReactNode, useMemo } from 'react';
import { PanelRightClose, PanelRightOpen } from 'lucide-react';
import { Button } from '$/components/ui/button';
import { LucideIcon } from '$/components/common/LucideIcon';
import { translateAppName, formatDate, filename } from '$/lib/utils';
import { entityFileUrl, entityVideoUrl } from '$/lib/api/entities';
import type { Entity } from '$/lib/api/types';

interface Props {
  entity: Entity | null;
  showDetails: boolean;
  toggleDetails: () => void;
  leftIcon?: ReactNode;
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

export function EntityImage({
  entity,
  showDetails,
  toggleDetails,
  leftIcon,
  rightAction,
}: Props) {
  const displayTitle = entity ? getEntityTitle(entity) : 'unknown';
  const displayAppName = entity ? getAppName(entity) : 'unknown';
  const formattedCreatedAt = useMemo(
    () => (entity?.file_created_at ? formatDate(entity.file_created_at) : ''),
    [entity?.file_created_at],
  );
  const videoUrl = entity?.filepath ? entityVideoUrl(entity) : undefined;
  const imageUrl = entity?.filepath ? entityFileUrl(entity) : '';

  return (
    <div
      className={`flex flex-col lg:h-full lg:flex-none ${
        showDetails ? 'w-full lg:w-1/2' : 'w-full'
      }`}
    >
      <div className="relative z-[52] mb-2 flex w-full items-center gap-2">
        <div className="flex-none">{leftIcon}</div>
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
            className="h-8 w-8 text-muted-foreground hover:text-foreground"
            onClick={toggleDetails}
            aria-label={showDetails ? 'Hide details' : 'Show details'}
            title={showDetails ? 'Hide details' : 'Show details'}
          >
            {showDetails ? <PanelRightClose size={18} /> : <PanelRightOpen size={18} />}
          </Button>
          {rightAction}
        </div>
      </div>

      {showDetails && entity && (
        <div className="mb-2 mr-2 border-b pb-2">
          <div className="font-mono text-xs leading-tight text-muted-foreground">
            <span className="text-foreground">№ {entity.id}</span>
            <span className="mx-2 opacity-50">·</span>
            <span>{formattedCreatedAt}</span>
          </div>
          {entity.filepath && (
            <div className="mt-1 break-all font-mono text-[11px] leading-tight text-muted-foreground">
              {entity.filepath}
            </div>
          )}
        </div>
      )}

      <div
        className={`relative flex items-center justify-center overflow-hidden lg:flex-1 ${
          showDetails ? 'lg:mr-2' : ''
        }`}
      >
        <a
          href={videoUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex w-full items-center justify-center lg:h-full"
        >
          <img
            className="max-h-[55vh] w-full rounded-lg object-contain drop-shadow-md lg:h-full lg:max-h-none"
            src={imageUrl}
            alt={displayTitle}
          />
        </a>
      </div>
    </div>
  );
}
