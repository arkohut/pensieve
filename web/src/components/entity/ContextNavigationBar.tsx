import { useEffect, useRef } from 'react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '$/components/ui/tooltip';
import { formatDate } from '$/lib/utils';
import { entityThumbnailUrl } from '$/lib/api/entities';
import type { Entity } from '$/lib/api/types';
import type { EntityContext } from '$/lib/api/entities';

interface Props {
  entity: Entity;
  contextData: EntityContext;
  onSelectEntity: (entity: Entity) => void;
}

function tooltipText(e: Entity): string {
  const screen = e.metadata_entries?.find((m) => m.key === 'screen_name')?.value ?? '';
  const app = e.metadata_entries?.find((m) => m.key === 'active_app')?.value ?? '';
  return `${screen} ${app} ${formatDate(e.file_created_at)}`.trim();
}

export function ContextNavigationBar({ entity, contextData, onSelectEntity }: Props) {
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    function onWheel(e: WheelEvent) {
      if (!el) return;
      if (Math.abs(e.deltaY) >= 10 && e.deltaMode === 0) {
        e.preventDefault();
        el.scrollLeft += e.deltaY;
      }
    }
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => {
      el.removeEventListener('wheel', onWheel);
    };
  }, []);

  function handleClick(contextEntity: Entity, e: React.MouseEvent) {
    e.preventDefault();
    onSelectEntity(contextEntity);
  }

  return (
    <div className="flex h-full w-full items-center">
      <div ref={scrollRef} className="w-full overflow-x-auto px-2">
        <div className="flex min-w-max items-center justify-start gap-3 pb-2">
          <TooltipProvider delayDuration={0}>
            {contextData.prev.map((ce) => (
              <div key={ce.id} className="h-24 w-24 flex-none">
                <Tooltip>
                  <TooltipTrigger className="h-full w-full">
                    <a
                      href={`/entities/${ce.id}`}
                      onClick={(e) => handleClick(ce, e)}
                      className="block h-full w-full cursor-pointer overflow-hidden rounded-lg opacity-70 transition-opacity hover:opacity-100"
                    >
                      <img
                        src={entityThumbnailUrl(ce)}
                        alt=""
                        loading="lazy"
                        className="h-full w-full object-cover"
                      />
                    </a>
                  </TooltipTrigger>
                  <TooltipContent>{tooltipText(ce)}</TooltipContent>
                </Tooltip>
              </div>
            ))}

            <div className="h-28 w-28 flex-none overflow-hidden rounded-lg border-2 border-primary shadow-md">
              <Tooltip>
                <TooltipTrigger className="h-full w-full">
                  <img
                    src={entityThumbnailUrl(entity)}
                    alt=""
                    className="h-full w-full object-cover"
                  />
                </TooltipTrigger>
                <TooltipContent>{tooltipText(entity)}</TooltipContent>
              </Tooltip>
            </div>

            {contextData.next.map((ce) => (
              <div key={ce.id} className="h-24 w-24 flex-none">
                <Tooltip>
                  <TooltipTrigger className="h-full w-full">
                    <a
                      href={`/entities/${ce.id}`}
                      onClick={(e) => handleClick(ce, e)}
                      className="block h-full w-full cursor-pointer overflow-hidden rounded-lg opacity-70 transition-opacity hover:opacity-100"
                    >
                      <img
                        src={entityThumbnailUrl(ce)}
                        alt=""
                        loading="lazy"
                        className="h-full w-full object-cover"
                      />
                    </a>
                  </TooltipTrigger>
                  <TooltipContent>{tooltipText(ce)}</TooltipContent>
                </Tooltip>
              </div>
            ))}
          </TooltipProvider>
        </div>
      </div>
    </div>
  );
}
