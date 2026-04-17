import { type ReactNode, useMemo } from 'react';
import { IndentIncrease, Library, Folder, Hash, FileClock } from 'lucide-react';
import { LucideIcon } from '$/components/common/LucideIcon';
import { translateAppName, formatDate, filename } from '$/lib/utils';
import { entityFileUrl, entityVideoUrl } from '$/lib/api/entities';
import type { Entity } from '$/lib/api/types';

interface Props {
  entity: Entity | null;
  showDetails: boolean;
  toggleDetails: () => void;
  leftIcon?: ReactNode;
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

export function EntityImage({ entity, showDetails, toggleDetails, leftIcon }: Props) {
  const displayTitle = entity ? getEntityTitle(entity) : 'unknown';
  const displayAppName = entity ? getAppName(entity) : 'unknown';
  const formattedCreatedAt = useMemo(
    () => (entity?.file_created_at ? formatDate(entity.file_created_at) : ''),
    [entity?.file_created_at],
  );
  const videoUrl = entity?.filepath ? entityVideoUrl(entity) : undefined;
  const imageUrl = entity?.filepath ? entityFileUrl(entity) : '';

  return (
    <div className={`flex h-full flex-none flex-col ${showDetails ? 'w-full md:w-1/2' : 'w-full'}`}>
      <div className="relative z-[52] mb-2">
        <div className="flex w-full items-center text-lg font-medium leading-tight text-black">
          <div className="flex w-full items-center justify-between">
            <div className="flex-none">{leftIcon}</div>
            <div className="flex min-w-0 flex-1 items-center justify-center">
              <div className="flex min-w-0 items-center space-x-2">
                <LucideIcon name={translateAppName(displayAppName) ?? 'Image'} size={24} />
                <p className="max-w-[500px] truncate">{displayTitle}</p>
                {!showDetails && formattedCreatedAt && (
                  <span className="inline-flex items-center pl-4 font-mono text-sm text-muted-foreground">
                    <FileClock size={16} className="mr-1 text-muted-foreground" />
                    {formattedCreatedAt}
                  </span>
                )}
              </div>
            </div>
            <button
              type="button"
              className="flex-none rounded-full p-2 transition-colors hover:bg-accent"
              onClick={toggleDetails}
              aria-label="Toggle details"
            >
              <IndentIncrease
                size={24}
                className={showDetails ? 'text-primary' : 'text-muted-foreground'}
              />
            </button>
          </div>
        </div>
      </div>

      {showDetails && entity && (
        <div className="mb-2 mr-2 border-b pb-2">
          <span className="mt-1 font-mono text-sm font-medium leading-tight text-muted-foreground">
            <span className="mr-4 inline-flex">
              <Library
                size={16}
                className="mr-1 text-sm font-bold uppercase tracking-wide text-primary"
              />
              {entity.library_id || ''}
            </span>
            <span className="mr-4 inline-flex">
              <Folder
                size={16}
                className="mr-1 text-sm font-bold uppercase tracking-wide text-primary"
              />
              {entity.folder_id || ''}
            </span>
            <span className="mr-4 inline-flex">
              <Hash
                size={16}
                className="mr-1 text-sm font-bold uppercase tracking-wide text-primary"
              />
              {entity.id || ''}
            </span>
            <span className="mr-4 inline-flex">
              <FileClock
                size={16}
                className="mr-1 font-mono text-sm font-bold uppercase tracking-wide text-primary"
              />
              {formattedCreatedAt}
            </span>
          </span>
          <div>
            <span className="font-xs mt-1 font-mono text-xs leading-tight text-muted-foreground">
              {entity.filepath || ''}
            </span>
          </div>
        </div>
      )}

      <div
        className={`relative flex flex-1 items-center justify-center overflow-hidden ${showDetails ? 'mr-2' : ''}`}
      >
        <a
          href={videoUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex h-full w-full items-center justify-center"
        >
          <img
            className="h-full rounded-lg object-contain drop-shadow-md"
            src={imageUrl}
            alt={displayTitle}
          />
        </a>
      </div>
    </div>
  );
}
