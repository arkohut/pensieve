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
      <div className="divide-y divide-border">
        {entity.tags && entity.tags.length > 0 && (
          <Row label="tags">
            <div className="flex flex-wrap gap-1.5">
              {entity.tags.map((tag, i) => (
                <Tag key={i}>
                  {typeof tag === 'string' ? tag : ((tag as { name?: string }).name ?? '')}
                </Tag>
              ))}
            </div>
          </Row>
        )}

        {appNameEntry && (
          <Row label="application" source="system" copyText={appNameEntry.value || ''}>
            <span className="text-sm text-foreground">{appNameEntry.value || 'unknown'}</span>
          </Row>
        )}

        {displayEntries.map((entry) => {
          const isObject = typeof entry.value === 'object' && entry.value !== null;
          const copyText = isObject ? JSON.stringify(entry.value) : String(entry.value);

          if (isObject) {
            return (
              <div key={entry.key} className="py-3">
                <div className="mb-2 flex items-center justify-between">
                  <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-muted-foreground">
                    {entry.key}
                  </span>
                  <div className="flex items-center gap-2">
                    <SourcePill source={entry.source} />
                    <CopyToClipboard text={copyText} />
                  </div>
                </div>
                {isValidOCRDataStructure(entry.value) ? (
                  <OCRTable ocrData={entry.value} />
                ) : (
                  <pre className="max-h-80 overflow-y-auto rounded-md bg-secondary p-3 font-mono text-[11.5px] leading-relaxed text-foreground">
                    {JSON.stringify(entry.value, null, 2)}
                  </pre>
                )}
              </div>
            );
          }

          return (
            <Row key={entry.key} label={entry.key} source={entry.source} copyText={copyText}>
              <div className="prose prose-sm max-w-none break-words text-sm text-foreground prose-p:my-0">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {String(entry.value)}
                </ReactMarkdown>
              </div>
            </Row>
          );
        })}
      </div>
    </ScrollArea>
  );
}

interface RowProps {
  label: string;
  source?: string;
  copyText?: string;
  children: React.ReactNode;
}

function Row({ label, source, copyText, children }: RowProps) {
  return (
    <div className="grid grid-cols-[96px_1fr_auto] items-baseline gap-3 py-3">
      <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-muted-foreground">
        {label}
      </span>
      <div className="min-w-0">{children}</div>
      <div className="flex items-center gap-2">
        {source && <SourcePill source={source} />}
        {copyText !== undefined && <CopyToClipboard text={copyText} />}
      </div>
    </div>
  );
}

function Tag({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-0.5 font-mono text-[11px] text-foreground">
      <span className="text-brand">·</span>
      {children}
    </span>
  );
}

function SourcePill({ source }: { source: string }) {
  return (
    <span className="rounded-sm border border-border px-1.5 py-px font-mono text-[9.5px] uppercase tracking-[0.08em] text-muted-foreground">
      {source}
    </span>
  );
}
