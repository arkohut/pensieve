export interface ProcessingStatus {
  library_id: number;
  computed_at: string;
  window_hours: number;
  coverage_window: {
    total: number;
    fully_processed: number;
    pct: number;
  };
  backlog: {
    total_unprocessed: number;
    oldest_age_seconds: number | null;
  };
  watch: {
    is_alive: boolean;
    is_on_battery: boolean;
    is_within_idle_window: boolean;
    idle_window: [string, string];
  };
}

export type PillColor = 'green' | 'yellow' | 'red' | 'gray';

export type HeadlineKey =
  | 'watch_dead'
  | 'paused_battery'
  | 'paused_window'
  | 'backlog'
  | 'caught_up'
  | 'processing';

export interface PillState {
  color: PillColor;
  pctText: string;
  headlineKey: HeadlineKey;
  headline: string;
}

const FIVE_MIN = 5 * 60;
const ONE_HOUR = 60 * 60;

export function pillState(s: ProcessingStatus): PillState {
  const pct = s.coverage_window.pct;
  const oldest = s.backlog.oldest_age_seconds ?? 0;
  const anyPaused = s.watch.is_on_battery || !s.watch.is_within_idle_window;

  let headlineKey: HeadlineKey;
  if (!s.watch.is_alive) {
    headlineKey = 'watch_dead';
  } else if (s.watch.is_on_battery) {
    headlineKey = 'paused_battery';
  } else if (!s.watch.is_within_idle_window) {
    headlineKey = 'paused_window';
  } else if (oldest > ONE_HOUR) {
    headlineKey = 'backlog';
  } else if (pct >= 0.95 && oldest <= FIVE_MIN) {
    headlineKey = 'caught_up';
  } else {
    headlineKey = 'processing';
  }

  let color: PillColor;
  if (!s.watch.is_alive || (anyPaused && oldest > FIVE_MIN)) {
    color = 'gray';
  } else {
    const cPct: PillColor = pct >= 0.95 ? 'green' : pct >= 0.8 ? 'yellow' : 'red';
    const cAge: PillColor = oldest <= FIVE_MIN ? 'green' : oldest <= ONE_HOUR ? 'yellow' : 'red';
    color = worst(cPct, cAge);
  }

  const pctText = `${Math.round(pct * 100)}%`;
  return { color, pctText, headlineKey, headline: HEADLINES[headlineKey](s) };
}

function worst(a: PillColor, b: PillColor): PillColor {
  const rank: Record<PillColor, number> = { green: 0, yellow: 1, red: 2, gray: 3 };
  return rank[a] >= rank[b] ? a : b;
}

const HEADLINES: Record<HeadlineKey, (s: ProcessingStatus) => string> = {
  watch_dead: () => 'Watch 服务未启动',
  paused_battery: () => '已暂停',
  paused_window: () => '已暂停',
  backlog: () => '处理积压',
  caught_up: () => '已跟上',
  processing: () => '处理中',
};

export function headlineReason(s: ProcessingStatus, key: HeadlineKey): string | null {
  if (key === 'paused_battery') return '电池供电中';
  if (key === 'paused_window') {
    const [a, b] = s.watch.idle_window;
    return `处理时段外（${a}–${b}）`;
  }
  return null;
}

export function humanizeAge(seconds: number | null): string {
  if (seconds === null || seconds < 0) return '—';
  if (seconds < 60) return `${seconds} 秒前`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} 分钟前`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)} 小时前`;
  return `${Math.round(seconds / 86400)} 天前`;
}

export function humanizeComputedAt(iso: string): string {
  const t = new Date(iso).getTime();
  const ageSec = Math.max(0, Math.round((Date.now() - t) / 1000));
  if (ageSec < 5) return '刚刚更新';
  if (ageSec < 60) return `${ageSec} 秒前更新`;
  if (ageSec < 3600) return `${Math.round(ageSec / 60)} 分钟前更新`;
  return `${Math.round(ageSec / 3600)} 小时前更新`;
}

