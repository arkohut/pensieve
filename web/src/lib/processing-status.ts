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

export const MOCK_PAYLOADS: Record<string, ProcessingStatus> = {
  processing: {
    library_id: 6,
    computed_at: new Date(Date.now() - 5000).toISOString(),
    window_hours: 24,
    coverage_window: { total: 4267, fully_processed: 3520, pct: 0.825 },
    backlog: { total_unprocessed: 1247, oldest_age_seconds: 35 * 60 },
    watch: {
      is_alive: true,
      is_on_battery: false,
      is_within_idle_window: true,
      idle_window: ['00:00', '23:59'],
    },
  },
  caught_up: {
    library_id: 6,
    computed_at: new Date(Date.now() - 2000).toISOString(),
    window_hours: 24,
    coverage_window: { total: 3984, fully_processed: 3962, pct: 0.9945 },
    backlog: { total_unprocessed: 22, oldest_age_seconds: 90 },
    watch: {
      is_alive: true,
      is_on_battery: false,
      is_within_idle_window: true,
      idle_window: ['00:00', '23:59'],
    },
  },
  backlog: {
    library_id: 6,
    computed_at: new Date(Date.now() - 8000).toISOString(),
    window_hours: 24,
    coverage_window: { total: 5102, fully_processed: 3210, pct: 0.6291 },
    backlog: { total_unprocessed: 4218, oldest_age_seconds: 4 * 3600 + 15 * 60 },
    watch: {
      is_alive: true,
      is_on_battery: false,
      is_within_idle_window: true,
      idle_window: ['00:00', '23:59'],
    },
  },
  paused_battery: {
    library_id: 6,
    computed_at: new Date(Date.now() - 12000).toISOString(),
    window_hours: 24,
    coverage_window: { total: 4267, fully_processed: 3702, pct: 0.8676 },
    backlog: { total_unprocessed: 685, oldest_age_seconds: 52 * 60 },
    watch: {
      is_alive: true,
      is_on_battery: true,
      is_within_idle_window: true,
      idle_window: ['00:00', '23:59'],
    },
  },
  paused_window: {
    library_id: 6,
    computed_at: new Date(Date.now() - 18000).toISOString(),
    window_hours: 24,
    coverage_window: { total: 4267, fully_processed: 3920, pct: 0.9187 },
    backlog: { total_unprocessed: 419, oldest_age_seconds: 80 * 60 },
    watch: {
      is_alive: true,
      is_on_battery: false,
      is_within_idle_window: false,
      idle_window: ['00:00', '07:00'],
    },
  },
  watch_dead: {
    library_id: 6,
    computed_at: new Date(Date.now() - 25000).toISOString(),
    window_hours: 24,
    coverage_window: { total: 4267, fully_processed: 3520, pct: 0.825 },
    backlog: { total_unprocessed: 1247, oldest_age_seconds: 3 * 3600 + 5 * 60 },
    watch: {
      is_alive: false,
      is_on_battery: false,
      is_within_idle_window: true,
      idle_window: ['00:00', '23:59'],
    },
  },
};

export const MOCK_ORDER: Array<keyof typeof MOCK_PAYLOADS> = [
  'processing',
  'caught_up',
  'backlog',
  'paused_battery',
  'paused_window',
  'watch_dead',
];

export const MOCK_LABELS: Record<string, string> = {
  processing: '处理中 (yellow)',
  caught_up: '已跟上 (green)',
  backlog: '处理积压 (red)',
  paused_battery: '电池暂停 (gray)',
  paused_window: '时段外暂停 (gray)',
  watch_dead: 'Watch 挂了 (gray)',
};
