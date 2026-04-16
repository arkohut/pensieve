import { describe, it, expect } from 'vitest';
import { cn, translateAppName, filename, formatDate } from '$/lib/utils';

describe('cn', () => {
  it('merges tailwind classes', () => {
    expect(cn('p-2', 'p-4')).toBe('p-4');
  });
});

describe('translateAppName', () => {
  it('maps known lowercased app name', () => {
    expect(translateAppName('Chrome')).toBe('Chrome');
    expect(translateAppName('iterm2')).toBe('SquareTerminal');
  });

  it('strips .exe suffix', () => {
    expect(translateAppName('chrome.exe')).toBe('Chrome');
  });

  it('returns undefined for unknown', () => {
    expect(translateAppName('SomeUnknownApp')).toBeUndefined();
  });
});

describe('filename', () => {
  it('extracts last segment', () => {
    expect(filename('/a/b/c.png')).toBe('c.png');
    expect(filename('single')).toBe('single');
  });
});

describe('formatDate', () => {
  it('returns empty string for empty input', () => {
    expect(formatDate('')).toBe('');
  });
});
