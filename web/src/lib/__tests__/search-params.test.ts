import { describe, it, expect } from 'vitest';
import { searchSchema, buildSearchPath } from '$/lib/search-params';

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
});
