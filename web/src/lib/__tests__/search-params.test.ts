import { describe, it, expect } from 'vitest';
import {
  buildSearchPath,
  effectiveSearchParams,
  searchSchema,
  type SearchParams,
} from '$/lib/search-params';

describe('searchSchema', () => {
  it('parses empty object with defaults', () => {
    const parsed = searchSchema.parse({});
    expect(parsed).toEqual({
      q: '',
      submitted_q: '',
      library_ids: [],
      app_names: [],
    });
  });

  it('coerces library_ids numbers from strings', () => {
    const parsed = searchSchema.parse({ library_ids: ['1', '2', '3'] });
    expect(parsed.library_ids).toEqual([1, 2, 3]);
  });

  it('preserves start/end when positive', () => {
    const parsed = searchSchema.parse({ start: 1712000000, end: 1713000000 });
    expect(parsed.start).toBe(1712000000);
    expect(parsed.end).toBe(1713000000);
  });

  it('catches malformed q with default empty string', () => {
    const parsed = searchSchema.parse({ q: 123 });
    expect(parsed.q).toBe('');
  });

  it('catches malformed library_ids with default empty array', () => {
    const parsed = searchSchema.parse({ library_ids: 'oops' });
    expect(parsed.library_ids).toEqual([]);
  });

  it('coerces open to a positive integer', () => {
    const parsed = searchSchema.parse({ open: '1684643' });
    expect(parsed.open).toBe(1684643);
  });

  it('drops invalid open values via catch', () => {
    const parsed = searchSchema.parse({ open: 'not-a-number' });
    expect(parsed.open).toBeUndefined();
  });

  it('omits open by default', () => {
    const parsed = searchSchema.parse({});
    expect(parsed.open).toBeUndefined();
  });
});

describe('buildSearchPath', () => {
  it('encodes only non-empty params', () => {
    const path = buildSearchPath({
      q: 'figma',
      submitted_q: 'figma',
      library_ids: [],
      app_names: [],
    });
    expect(path).toBe('/search?q=figma');
  });

  it('preserves seconds for start/end', () => {
    const path = buildSearchPath({
      q: '',
      submitted_q: '',
      start: 1712000000,
      end: 1713000000,
      library_ids: [],
      app_names: [],
    });
    expect(path).toContain('start=1712000000');
    expect(path).toContain('end=1713000000');
  });

  it('joins arrays with comma', () => {
    const path = buildSearchPath({
      q: '',
      submitted_q: '',
      library_ids: [1, 3],
      app_names: ['Figma', 'Chrome'],
    });
    expect(path).toContain('library_ids=1%2C3');
    expect(path).toContain('app_names=Figma%2CChrome');
  });

  it('drops start=0 sentinel from the wire format', () => {
    const path = buildSearchPath({
      q: '',
      submitted_q: '',
      start: 0,
      library_ids: [],
      app_names: [],
    });
    expect(path).not.toContain('start=');
  });
});

describe('effectiveSearchParams', () => {
  const base: SearchParams = {
    q: '',
    submitted_q: '',
    library_ids: [],
    app_names: [],
  };
  const NOW = 1_715_000_000; // arbitrary fixed epoch
  const NINETY_DAYS = 90 * 24 * 60 * 60;

  it('applies the 3-month default when nothing is set', () => {
    expect(effectiveSearchParams(base, NOW).start).toBe(NOW - NINETY_DAYS);
  });

  it('strips the start=0 sentinel without applying the default', () => {
    const out = effectiveSearchParams({ ...base, start: 0 }, NOW);
    expect(out.start).toBeUndefined();
    expect(out.end).toBeUndefined();
  });

  it('leaves an explicit start untouched', () => {
    const out = effectiveSearchParams({ ...base, start: 1234567 }, NOW);
    expect(out.start).toBe(1234567);
  });

  it('skips the default when only end is set', () => {
    const out = effectiveSearchParams({ ...base, end: 1234567 }, NOW);
    expect(out.start).toBeUndefined();
    expect(out.end).toBe(1234567);
  });

  it('skips the default when a date facet is selected', () => {
    const out = effectiveSearchParams({ ...base, date: '2026-04' }, NOW);
    expect(out.start).toBeUndefined();
    expect(out.date).toBe('2026-04');
  });
});
