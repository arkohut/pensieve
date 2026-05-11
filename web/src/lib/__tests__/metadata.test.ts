import { describe, expect, it } from 'vitest';
import {
  HIDDEN_KEYS,
  displayOrder,
  processEntries,
  shortSource,
  type ProcessedEntry,
} from '$/lib/metadata';
import type { MetadataEntry } from '$/lib/api/types';

function entry(
  key: string,
  value: string,
  data_type: MetadataEntry['data_type'] = 'text',
  source = 'system_generated',
): MetadataEntry {
  return { key, value, data_type, source };
}

describe('processEntries', () => {
  it('returns empty for undefined input', () => {
    expect(processEntries(undefined)).toEqual([]);
  });

  it('parses data_type=json values into objects', () => {
    const out = processEntries([entry('m', '{"a":1,"b":[2,3]}', 'json')]);
    expect(out[0].value).toEqual({ a: 1, b: [2, 3] });
  });

  it('falls back to the raw string when json data_type fails to parse', () => {
    const out = processEntries([entry('m', '{not valid', 'json')]);
    expect(out[0].value).toBe('{not valid');
  });

  it('reparses text-typed entries whose string is actually a JSON object', () => {
    const out = processEntries([entry('m', '{"extractor":"vlm","ok":true}', 'text')]);
    expect(out[0].value).toEqual({ extractor: 'vlm', ok: true });
  });

  it('reparses text-typed entries whose string is a JSON array', () => {
    const out = processEntries([entry('m', '[1, 2, 3]', 'text')]);
    expect(out[0].value).toEqual([1, 2, 3]);
  });

  it('leaves plain markdown text alone even if it contains braces', () => {
    const out = processEntries([entry('m', 'use the `{x}` placeholder', 'text')]);
    expect(out[0].value).toBe('use the `{x}` placeholder');
  });

  it('does not reparse strings that merely start with { but are not JSON', () => {
    const out = processEntries([entry('m', '{ this looks like JSON but isnt }', 'text')]);
    expect(out[0].value).toBe('{ this looks like JSON but isnt }');
  });

  it('handles mixed data_types within one batch', () => {
    const out = processEntries([
      entry('a', 'plain', 'text'),
      entry('b', '{"k":1}', 'json'),
      entry('c', '[1,2]', 'text'), // gets sniffed
      entry('d', '42', 'number'),
    ]);
    expect(out.map((e) => e.value)).toEqual(['plain', { k: 1 }, [1, 2], '42']);
  });

  it('preserves source and other metadata fields', () => {
    const out = processEntries([entry('m', '{"x":1}', 'json', 'vlm')]);
    expect(out[0].source).toBe('vlm');
    expect(out[0].data_type).toBe('json');
    expect(out[0].key).toBe('m');
  });
});

describe('HIDDEN_KEYS', () => {
  it('hides the expected system-level keys', () => {
    for (const key of ['timestamp', 'sequence', 'active_app', 'active_window']) {
      expect(HIDDEN_KEYS.has(key)).toBe(true);
    }
  });

  it('keeps useful keys visible', () => {
    for (const key of ['screen_name', 'ocr_result', 'url', 'qwen3.6_35b_result']) {
      expect(HIDDEN_KEYS.has(key)).toBe(false);
    }
  });
});

describe('displayOrder', () => {
  function key(k: string): ProcessedEntry {
    return { key: k, value: '', data_type: 'text', source: 'system_generated' };
  }

  it('pins screen_name to the top', () => {
    const sorted = [key('url'), key('screen_name'), key('ocr_result')].sort(displayOrder);
    expect(sorted[0].key).toBe('screen_name');
  });

  it('pins ocr_result to the bottom', () => {
    const sorted = [key('ocr_result'), key('url'), key('screen_name')].sort(displayOrder);
    expect(sorted.at(-1)?.key).toBe('ocr_result');
  });

  it('leaves unrelated keys in their relative order', () => {
    const sorted = [key('a'), key('b'), key('c'), key('screen_name')].sort(displayOrder);
    expect(sorted.map((e) => e.key)).toEqual(['screen_name', 'a', 'b', 'c']);
  });
});

describe('shortSource', () => {
  it('maps system_generated to system', () => {
    expect(shortSource('system_generated')).toBe('system');
  });

  it('passes through unknown sources unchanged', () => {
    expect(shortSource('vlm')).toBe('vlm');
    expect(shortSource('structured_vlm')).toBe('structured_vlm');
    expect(shortSource('ocr')).toBe('ocr');
  });
});
