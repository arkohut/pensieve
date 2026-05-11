import type { MetadataEntry } from '$/lib/api/types';

export interface ProcessedEntry extends Omit<MetadataEntry, 'value'> {
  value: string | unknown;
}

/**
 * Decode a metadata entry's value. JSON-typed entries are parsed; text-typed
 * entries whose value happens to be a JSON object/array are also reparsed so
 * the UI can pretty-print them. Anything that doesn't decode cleanly stays as
 * the original string.
 */
export function processEntries(entries: MetadataEntry[] | undefined): ProcessedEntry[] {
  if (!entries) return [];
  return entries.map((entry) => {
    const processed: ProcessedEntry = { ...entry };
    if (entry.data_type === 'json') {
      try {
        processed.value = JSON.parse(entry.value);
      } catch {
        // Malformed JSON falls back to the raw string so the UI still renders
        // something instead of crashing the panel.
        processed.value = entry.value;
      }
      return processed;
    }
    if (typeof entry.value === 'string') {
      // Some pipelines (e.g. structured_vlm before its data_type fix) stored
      // JSON in entries marked data_type='text'. Opportunistically reparse so
      // those entries also render as pretty objects.
      const trimmed = entry.value.trim();
      const looksLikeJson =
        (trimmed.startsWith('{') && trimmed.endsWith('}')) ||
        (trimmed.startsWith('[') && trimmed.endsWith(']'));
      if (looksLikeJson) {
        try {
          const parsed: unknown = JSON.parse(trimmed);
          if (parsed !== null && typeof parsed === 'object') {
            processed.value = parsed;
          }
        } catch {
          // Looks like JSON but isn't. Leave the original string in place.
        }
      }
    }
    return processed;
  });
}

/**
 * Keys filtered out of the visible metadata list. They're either rendered
 * elsewhere (active_app, active_window) or surfaced as identifier metadata
 * (timestamp, sequence).
 */
export const HIDDEN_KEYS: ReadonlySet<string> = new Set([
  'timestamp',
  'sequence',
  'active_app',
  'active_window',
]);

/**
 * Sort comparator that pins screen_name to the top and ocr_result to the
 * bottom while leaving the rest in their original order.
 */
export function displayOrder(a: ProcessedEntry, b: ProcessedEntry): number {
  if (a.key === 'screen_name') return -1;
  if (b.key === 'screen_name') return 1;
  if (a.key === 'ocr_result') return 1;
  if (b.key === 'ocr_result') return -1;
  return 0;
}

const SOURCE_LABELS: Record<string, string> = {
  system_generated: 'system',
};

/**
 * Map raw source names from the backend to compact display labels used in
 * source pills. Unknown sources are returned untouched.
 */
export function shortSource(source: string): string {
  return SOURCE_LABELS[source] ?? source;
}
