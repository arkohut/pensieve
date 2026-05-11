import { useMemo } from 'react';
import { formatDate, filename } from '$/lib/utils';
import { entityFileUrl, entityVideoUrl } from '$/lib/api/entities';
import type { Entity } from '$/lib/api/types';

interface Props {
  entity: Entity | null;
  /** When true, render the identifier strip (id · date · filepath) above the image. */
  showIdentifier?: boolean;
  className?: string;
}

function getEntityTitle(doc: Entity): string {
  const aw = doc.metadata_entries?.find((e) => e.key === 'active_window');
  if (aw) return aw.value;
  return doc.filepath ? filename(doc.filepath) : '';
}

export function EntityImage({ entity, showIdentifier = true, className }: Props) {
  const displayTitle = entity ? getEntityTitle(entity) : 'unknown';
  const formattedCreatedAt = useMemo(
    () => (entity?.file_created_at ? formatDate(entity.file_created_at) : ''),
    [entity?.file_created_at],
  );
  const videoUrl = entity?.filepath ? entityVideoUrl(entity) : undefined;
  const imageUrl = entity?.filepath ? entityFileUrl(entity) : '';

  return (
    <div className={`flex min-w-0 flex-col ${className ?? ''}`}>
      {showIdentifier && entity && (
        <div className="mb-2 border-b pb-2">
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

      <div className="relative flex flex-1 items-center justify-center overflow-hidden">
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
            decoding="async"
          />
        </a>
      </div>
    </div>
  );
}
