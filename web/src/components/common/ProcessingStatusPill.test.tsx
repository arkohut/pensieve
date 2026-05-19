import { render, screen } from '@testing-library/react';
import { describe, expect, test } from 'vitest';

import { PillButton } from './ProcessingStatusPill';
import type { ProcessingStatus } from '$/lib/processing-status';

function fixture(overrides: Partial<ProcessingStatus> = {}): ProcessingStatus {
  const base: ProcessingStatus = {
    library_id: 1,
    computed_at: new Date().toISOString(),
    window_hours: 24,
    coverage_window: { total: 100, fully_processed: 82, pct: 0.82 },
    backlog: { total_unprocessed: 18, oldest_age_seconds: 600 },
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

describe('PillButton', () => {
  test('renders percentage text', () => {
    render(<PillButton status={fixture()} />);
    expect(screen.getByText('82%')).toBeTruthy();
  });

  test('aria-label reflects headline', () => {
    render(
      <PillButton
        status={fixture({
          watch: {
            is_alive: false,
            is_on_battery: false,
            is_within_idle_window: true,
            idle_window: ['00:00', '23:59'],
          },
        })}
      />,
    );
    const btn = screen.getByRole('button');
    expect(btn.getAttribute('aria-label')).toContain('Watch 服务未启动');
  });
});
