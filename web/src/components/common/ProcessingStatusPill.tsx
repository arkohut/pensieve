import { useMemo } from 'react';

import { Popover, PopoverContent, PopoverTrigger } from '$/components/ui/popover';
import { useLibraries } from '$/lib/api/libraries';
import { useProcessingStatus } from '$/lib/api/processing-status';
import {
  headlineReason,
  humanizeAge,
  humanizeComputedAt,
  pillState,
  type PillColor,
  type ProcessingStatus,
} from '$/lib/processing-status';
import { cn } from '$/lib/utils';

const DOT_CLASS: Record<PillColor, string> = {
  green: 'bg-emerald-500',
  yellow: 'bg-amber-500',
  red: 'bg-red-500',
  gray: 'bg-zinc-400',
};

export function ProcessingStatusPill() {
  const { data: libraries } = useLibraries();
  const recordLibraryId = useMemo(
    () => libraries?.find((l) => l.kind === 'record')?.id,
    [libraries],
  );
  const { data: status } = useProcessingStatus(recordLibraryId);

  if (!status) return null;
  return <PillButton status={status} />;
}

export function PillButton({ status }: { status: ProcessingStatus }) {
  const state = pillState(status);
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={`Processing status: ${state.headline}`}
          className={cn(
            'inline-flex h-8 items-center gap-1.5 rounded-full border border-border/70 bg-background px-2.5',
            'text-xs font-medium text-muted-foreground hover:text-foreground',
            'transition-colors hover:border-border focus-visible:outline-none focus-visible:ring-2',
            'focus-visible:ring-ring focus-visible:ring-offset-2',
          )}
        >
          <span className={cn('h-2 w-2 rounded-full', DOT_CLASS[state.color])} aria-hidden />
          <span className="tabular-nums">{state.pctText}</span>
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 p-0">
        <PanelBody status={status} />
      </PopoverContent>
    </Popover>
  );
}

function PanelBody({ status }: { status: ProcessingStatus }) {
  const state = pillState(status);
  const reason = headlineReason(status, state.headlineKey);
  const { coverage_window: cov, backlog, watch } = status;

  return (
    <div className="text-sm">
      <div className="flex items-baseline justify-between px-4 pt-3.5 pb-2">
        <div className="flex items-center gap-2">
          <span className={cn('h-2.5 w-2.5 rounded-full', DOT_CLASS[state.color])} aria-hidden />
          <span className="font-medium text-foreground">{state.headline}</span>
          {reason && <span className="text-[11px] text-muted-foreground">{reason}</span>}
        </div>
        <span className="text-[11px] text-muted-foreground">
          {humanizeComputedAt(status.computed_at)}
        </span>
      </div>

      <Divider />

      <div className="px-4 py-3">
        <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
          近 {status.window_hours} 小时新增
        </div>
        <div className="mt-1 flex items-baseline gap-2">
          <span className="text-2xl font-semibold tabular-nums text-foreground">
            {(cov.pct * 100).toFixed(1)}%
          </span>
        </div>
        <div className="mt-0.5 text-xs text-muted-foreground">
          {cov.fully_processed.toLocaleString()} / {cov.total.toLocaleString()} 已全部完成插件
        </div>
      </div>

      <Divider />

      <div className="px-4 py-3">
        <div className="text-[11px] uppercase tracking-wider text-muted-foreground">历史积压</div>
        <div className="mt-1 text-foreground">
          <span className="font-semibold tabular-nums">
            {backlog.total_unprocessed.toLocaleString()}
          </span>{' '}
          <span className="text-muted-foreground">条</span>
          {backlog.oldest_age_seconds !== null && (
            <>
              <span className="mx-1.5 text-muted-foreground">·</span>
              <span className="text-muted-foreground">
                最老 {humanizeAge(backlog.oldest_age_seconds)}
              </span>
            </>
          )}
        </div>
      </div>

      <Divider />

      <div className="px-4 py-2.5 text-[11px] text-muted-foreground">
        <WatchFactLine watch={watch} />
      </div>
    </div>
  );
}

function WatchFactLine({ watch }: { watch: ProcessingStatus['watch'] }) {
  const parts: string[] = [];
  parts.push(watch.is_alive ? 'Watch 运行中' : 'Watch 未启动');
  parts.push(watch.is_on_battery ? '电池供电' : '已接电源');
  parts.push(`时段 ${watch.idle_window[0]}–${watch.idle_window[1]}`);
  return <span>{parts.join(' · ')}</span>;
}

function Divider() {
  return <div className="h-px bg-border/70" />;
}
