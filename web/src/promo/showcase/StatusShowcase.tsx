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

export function PillStandalone({ status }: { status: ProcessingStatus }) {
  const state = pillState(status);
  return (
    <button
      type="button"
      className={cn(
        'inline-flex h-8 items-center gap-1.5 rounded-full border border-border/70 bg-background px-2.5',
        'text-xs font-medium text-muted-foreground',
      )}
    >
      <span className={cn('h-2 w-2 rounded-full', DOT_CLASS[state.color])} aria-hidden />
      <span className="tabular-nums">{state.pctText}</span>
    </button>
  );
}

export function PanelStandalone({ status }: { status: ProcessingStatus }) {
  const state = pillState(status);
  const reason = headlineReason(status, state.headlineKey);
  const { coverage_window: cov, backlog, watch } = status;
  return (
    <div className="w-80 rounded-md border border-border bg-popover text-sm shadow-md">
      <div className="flex items-baseline justify-between px-4 pb-2 pt-3.5">
        <div className="flex items-center gap-2">
          <span
            className={cn('h-2.5 w-2.5 rounded-full', DOT_CLASS[state.color])}
            aria-hidden
          />
          <span className="font-medium text-foreground">{state.headline}</span>
          {reason && <span className="text-[11px] text-muted-foreground">{reason}</span>}
        </div>
        <span className="text-[11px] text-muted-foreground">
          {humanizeComputedAt(status.computed_at)}
        </span>
      </div>
      <div className="h-px bg-border/70" />
      <div className="px-4 py-3">
        <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
          过去 {status.window_hours} 小时
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
      <div className="h-px bg-border/70" />
      <div className="px-4 py-3">
        <div className="text-[11px] uppercase tracking-wider text-muted-foreground">待处理</div>
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
      <div className="h-px bg-border/70" />
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
