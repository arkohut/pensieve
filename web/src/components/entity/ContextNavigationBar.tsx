import { useEffect, useMemo, useRef } from 'react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '$/components/ui/tooltip';
import { cn, formatDate } from '$/lib/utils';
import { entityThumbnailUrl } from '$/lib/api/entities';
import type { Entity } from '$/lib/api/types';
import type { EntityContext } from '$/lib/api/entities';

interface Props {
  entity: Entity;
  contextData: EntityContext;
  onSelectEntity: (entity: Entity) => void;
}

function shortTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  const ss = String(d.getSeconds()).padStart(2, '0');
  return `${hh}:${mm}:${ss}`;
}

function tooltipText(e: Entity): string {
  const screen = e.metadata_entries?.find((m) => m.key === 'screen_name')?.value ?? '';
  const app = e.metadata_entries?.find((m) => m.key === 'active_app')?.value ?? '';
  return `${screen} ${app} ${formatDate(e.file_created_at)}`.trim();
}

export function ContextNavigationBar({ entity, contextData, onSelectEntity }: Props) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const currentRef = useRef<HTMLDivElement | null>(null);

  const timeline = useMemo(
    () => [...contextData.prev, entity, ...contextData.next],
    [contextData.prev, contextData.next, entity],
  );

  // Vertical wheel scrolls the strip horizontally — trackpads and mice both
  // produce deltaY here, so map it onto scrollLeft.
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

  // Re-center the current frame when navigating between adjacent entities.
  useEffect(() => {
    currentRef.current?.scrollIntoView({ block: 'nearest', inline: 'center' });
  }, [entity.id]);

  function handleClick(ce: Entity, e: React.MouseEvent) {
    e.preventDefault();
    onSelectEntity(ce);
  }

  const first = timeline[0];
  const last = timeline.at(-1);

  return (
    <div className="flex h-full w-full flex-col">
      <div className="mb-1 flex items-center justify-between px-4 font-mono text-[10.5px] uppercase tracking-[0.08em] text-muted-foreground">
        <span>
          <span className="opacity-60">← →</span> navigate
          <span className="mx-2 opacity-40">·</span>
          <span className="opacity-60">esc</span> home
        </span>
        {first && last && (
          <span>
            <strong className="font-medium text-foreground">
              {shortTime(first.file_created_at)}
            </strong>
            <span className="mx-2 opacity-40">→</span>
            <strong className="font-medium text-foreground">
              {shortTime(last.file_created_at)}
            </strong>
            <span className="ml-3 opacity-60">· {timeline.length} frames</span>
          </span>
        )}
      </div>

      <div
        ref={scrollRef}
        className="flex-1 overflow-x-auto [mask-image:linear-gradient(90deg,transparent,#000_2%,#000_98%,transparent)] [-webkit-mask-image:linear-gradient(90deg,transparent,#000_2%,#000_98%,transparent)]"
      >
        <div className="flex min-w-max flex-col px-6">
          <div className="flex items-end gap-2 pt-2">
            <TooltipProvider delayDuration={150}>
              {timeline.map((ce) => {
                const isCur = ce.id === entity.id;
                return (
                  <div
                    key={ce.id}
                    ref={isCur ? currentRef : undefined}
                    className={cn(
                      'flex-none overflow-hidden rounded-md bg-black transition-all',
                      isCur
                        ? 'h-[80px] w-[132px] ring-2 ring-brand ring-offset-2 ring-offset-background'
                        : 'h-[56px] w-[92px] border border-border opacity-70 hover:opacity-100',
                    )}
                  >
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <a
                          href={`/entities/${ce.id}`}
                          onClick={(e) => handleClick(ce, e)}
                          className="block h-full w-full cursor-pointer"
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
                );
              })}
            </TooltipProvider>
          </div>

          <div className="mt-2 flex items-start gap-2 border-t border-border pt-1">
            {timeline.map((ce) => {
              const isCur = ce.id === entity.id;
              return (
                <span
                  key={ce.id}
                  className={cn(
                    'flex-none text-center font-mono text-[10px] tracking-wide tabular-nums',
                    isCur ? 'w-[132px] font-medium text-brand' : 'w-[92px] text-muted-foreground',
                  )}
                >
                  {shortTime(ce.file_created_at)}
                </span>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
