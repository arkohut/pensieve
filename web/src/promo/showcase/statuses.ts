import type { ProcessingStatus } from '$/lib/processing-status';

const NOW = Date.now();

export function makeStatus(overrides: Partial<ProcessingStatus>): ProcessingStatus {
  const base: ProcessingStatus = {
    library_id: 1,
    computed_at: new Date(NOW - 12_000).toISOString(),
    window_hours: 24,
    coverage_window: { total: 10294, fully_processed: 10294, pct: 1.0 },
    backlog: { total_unprocessed: 0, oldest_age_seconds: null },
    watch: {
      is_alive: true,
      is_on_battery: false,
      is_within_idle_window: true,
      idle_window: ['00:00', '23:59'],
    },
  };
  return {
    ...base,
    ...overrides,
    coverage_window: { ...base.coverage_window, ...(overrides.coverage_window ?? {}) },
    backlog: { ...base.backlog, ...(overrides.backlog ?? {}) },
    watch: { ...base.watch, ...(overrides.watch ?? {}) },
  };
}

export const STATUSES: ProcessingStatus[] = [
  makeStatus({}),
  makeStatus({
    coverage_window: { total: 10294, fully_processed: 9481, pct: 0.921 },
    backlog: { total_unprocessed: 813, oldest_age_seconds: 8 * 60 },
  }),
  makeStatus({
    coverage_window: { total: 10294, fully_processed: 6588, pct: 0.64 },
    backlog: { total_unprocessed: 3706, oldest_age_seconds: 2 * 3600 + 14 * 60 },
  }),
  makeStatus({
    coverage_window: { total: 10294, fully_processed: 9100, pct: 0.884 },
    backlog: { total_unprocessed: 1194, oldest_age_seconds: 22 * 60 },
    watch: {
      is_alive: true,
      is_on_battery: true,
      is_within_idle_window: true,
      idle_window: ['00:00', '23:59'],
    },
  }),
];

export const STATE_LABELS = ['Caught up', 'Processing', 'Backlog', 'Paused'];
