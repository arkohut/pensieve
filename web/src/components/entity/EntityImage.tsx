import { useEffect, useMemo, useState } from 'react';
import { cn, formatDate, filename } from '$/lib/utils';
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

  // Soft fade between images. If the next image is already in the browser
  // cache (we prefetch neighbors), `complete` is true synchronously and we
  // skip the transition. Otherwise we fade from the prior frame instead of
  // flashing a blank gap.
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    setLoaded(false);
  }, [imageUrl]);

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
            className={cn(
              'max-h-[55vh] w-full rounded-lg object-contain drop-shadow-md transition-opacity duration-150 lg:h-full lg:max-h-none',
              loaded ? 'opacity-100' : 'opacity-0',
            )}
            src={imageUrl}
            alt={displayTitle}
            decoding="async"
            onLoad={() => setLoaded(true)}
            ref={(el) => {
              // If the new src is already cached, `complete` is true before
              // onLoad ever fires — flip the state right away.
              if (el?.complete) setLoaded(true);
            }}
          />
        </a>
      </div>
    </div>
  );
}
