import { describe, expect, test } from 'vitest';
import {
  headlineReason,
  pillState,
  type ProcessingStatus,
} from './processing-status';

function fixture(overrides: Partial<ProcessingStatus> = {}): ProcessingStatus {
  const base: ProcessingStatus = {
    library_id: 1,
    computed_at: new Date().toISOString(),
    window_hours: 24,
    coverage_window: { total: 100, fully_processed: 100, pct: 1.0 },
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

describe('pillState', () => {
  test('green when 100% covered and no backlog', () => {
    const s = pillState(fixture());
    expect(s.color).toBe('green');
    expect(s.headlineKey).toBe('caught_up');
    expect(s.pctText).toBe('100%');
  });

  test('yellow at 90% coverage with fresh backlog', () => {
    const s = pillState(
      fixture({
        coverage_window: { total: 100, fully_processed: 90, pct: 0.9 },
        backlog: { total_unprocessed: 10, oldest_age_seconds: 60 },
      }),
    );
    expect(s.color).toBe('yellow');
    expect(s.headlineKey).toBe('processing');
  });

  test('red when coverage below 80%', () => {
    const s = pillState(
      fixture({
        coverage_window: { total: 100, fully_processed: 70, pct: 0.7 },
        backlog: { total_unprocessed: 30, oldest_age_seconds: 10 * 60 },
      }),
    );
    expect(s.color).toBe('red');
    expect(s.headlineKey).toBe('processing');
  });

  test('red and backlog headline when oldest > 1h', () => {
    const s = pillState(
      fixture({
        coverage_window: { total: 100, fully_processed: 90, pct: 0.9 },
        backlog: { total_unprocessed: 10, oldest_age_seconds: 2 * 60 * 60 },
      }),
    );
    expect(s.color).toBe('red');
    expect(s.headlineKey).toBe('backlog');
  });

  test('gray when watch dead', () => {
    const s = pillState(
      fixture({
        watch: { is_alive: false, is_on_battery: false, is_within_idle_window: true, idle_window: ['00:00', '23:59'] },
        backlog: { total_unprocessed: 100, oldest_age_seconds: 60 * 60 },
      }),
    );
    expect(s.color).toBe('gray');
    expect(s.headlineKey).toBe('watch_dead');
  });

  test('gray when on battery and backlog older than 5min', () => {
    const s = pillState(
      fixture({
        watch: { is_alive: true, is_on_battery: true, is_within_idle_window: true, idle_window: ['00:00', '23:59'] },
        backlog: { total_unprocessed: 10, oldest_age_seconds: 10 * 60 },
        coverage_window: { total: 100, fully_processed: 90, pct: 0.9 },
      }),
    );
    expect(s.color).toBe('gray');
    expect(s.headlineKey).toBe('paused_battery');
  });

  test('not gray when on battery but oldest under 5min', () => {
    const s = pillState(
      fixture({
        watch: { is_alive: true, is_on_battery: true, is_within_idle_window: true, idle_window: ['00:00', '23:59'] },
        backlog: { total_unprocessed: 1, oldest_age_seconds: 30 },
        coverage_window: { total: 100, fully_processed: 99, pct: 0.99 },
      }),
    );
    expect(s.color).not.toBe('gray');
    expect(s.headlineKey).toBe('paused_battery');
  });

  test('paused_window headline when outside idle window', () => {
    const s = pillState(
      fixture({
        watch: { is_alive: true, is_on_battery: false, is_within_idle_window: false, idle_window: ['00:00', '07:00'] },
        backlog: { total_unprocessed: 50, oldest_age_seconds: 30 * 60 },
        coverage_window: { total: 100, fully_processed: 95, pct: 0.95 },
      }),
    );
    expect(s.headlineKey).toBe('paused_window');
    expect(s.color).toBe('gray');
  });

  test('empty window (total=0) treated as caught up', () => {
    const s = pillState(
      fixture({ coverage_window: { total: 0, fully_processed: 0, pct: 1.0 } }),
    );
    expect(s.headlineKey).toBe('caught_up');
    expect(s.color).toBe('green');
  });
});

describe('headlineReason', () => {
  test('returns null for non-paused keys', () => {
    expect(headlineReason(fixture(), 'caught_up')).toBeNull();
    expect(headlineReason(fixture(), 'processing')).toBeNull();
    expect(headlineReason(fixture(), 'backlog')).toBeNull();
    expect(headlineReason(fixture(), 'watch_dead')).toBeNull();
  });

  test('returns battery copy', () => {
    expect(headlineReason(fixture(), 'paused_battery')).toBe('电池供电中');
  });

  test('returns window copy with the configured range', () => {
    const s = fixture({
      watch: {
        is_alive: true,
        is_on_battery: false,
        is_within_idle_window: false,
        idle_window: ['22:00', '06:00'],
      },
    });
    expect(headlineReason(s, 'paused_window')).toBe('处理时段外（22:00–06:00）');
  });
});
