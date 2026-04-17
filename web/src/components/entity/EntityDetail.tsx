import { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ScrollArea } from '$/components/ui/scroll-area';
import { CopyToClipboard } from '$/components/common/CopyToClipboard';
import { OCRTable, isValidOCRDataStructure } from './OCRTable';
import type { Entity, MetadataEntry } from '$/lib/api/types';

interface ProcessedEntry extends Omit<MetadataEntry, 'value'> {
  value: string | unknown;
}

function processEntries(entries: MetadataEntry[] | undefined): ProcessedEntry[] {
  if (!entries) return [];
  return entries.map((entry) => {
    const processed: ProcessedEntry = { ...entry };
    if (entry.data_type === 'json') {
      try {
        processed.value = JSON.parse(entry.value);
      } catch (error) {
        console.error(`Error parsing JSON for key ${entry.key}:`, error);
        processed.value = entry.value;
      }
    }
    return processed;
  });
}

const HIDDEN_KEYS = new Set(['timestamp', 'sequence', 'active_app', 'active_window']);

function displayOrder(a: ProcessedEntry, b: ProcessedEntry): number {
  if (a.key === 'screen_name') return -1;
  if (b.key === 'screen_name') return 1;
  if (a.key === 'ocr_result') return 1;
  if (b.key === 'ocr_result') return -1;
  return 0;
}

interface Props {
  entity: Entity | null;
}

export function EntityDetail({ entity }: Props) {
  const displayEntries = useMemo(() => {
    const processed = processEntries(entity?.metadata_entries);
    return processed.filter((e) => !HIDDEN_KEYS.has(e.key)).sort(displayOrder);
  }, [entity?.metadata_entries]);

  const appNameEntry = entity?.metadata_entries?.find((e) => e.key === 'active_app');

  if (!entity) return null;

  return (
    <ScrollArea className="mt-4 max-h-[calc(100vh-180px)] overflow-y-auto md:ml-6 md:mt-0 md:w-1/2">
      {entity.tags && entity.tags.length > 0 && (
        <div className="mb-4">
          <div className="text-sm font-bold uppercase tracking-wide text-primary">TAGS</div>
          <div className="text-muted-foreground">
            {entity.tags.map((tag, i) => (
              <span key={i} className="mr-2 inline-block text-base text-muted-foreground">
                {typeof tag === 'string' ? tag : ((tag as { name?: string }).name ?? '')}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="text-sm font-bold uppercase tracking-wide text-primary">METADATA</div>
      <div className="mt-2 pb-4 text-muted-foreground">
        {displayEntries.map((entry) => {
          const isObject = typeof entry.value === 'object' && entry.value !== null;
          const copyText = isObject ? JSON.stringify(entry.value) : String(entry.value);
          return (
            <div key={entry.key} className="mb-2">
              <span className="flex items-center font-bold">
                {entry.key}
                <CopyToClipboard text={copyText} />
              </span>
              {isObject ? (
                isValidOCRDataStructure(entry.value) ? (
                  <OCRTable ocrData={entry.value} />
                ) : (
                  <pre className="max-h-80 overflow-y-auto rounded bg-muted p-2">
                    {JSON.stringify(entry.value, null, 2)}
                  </pre>
                )
              ) : (
                <div className="prose max-w-none">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {String(entry.value)}
                  </ReactMarkdown>
                </div>
              )}
              <span className="text-sm text-muted-foreground">({entry.source})</span>
            </div>
          );
        })}
      </div>

      {appNameEntry && (
        <>
          <div className="mt-6 text-sm font-bold uppercase tracking-wide text-primary">
            APP NAME
          </div>
          <div className="mb-4 flex items-center text-base text-foreground">
            {appNameEntry.value || 'unknown'}
            <CopyToClipboard text={appNameEntry.value || ''} />
          </div>
        </>
      )}
    </ScrollArea>
  );
}
