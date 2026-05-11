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
    } else if (typeof entry.value === 'string') {
      // Some pipelines (e.g. structured_vlm) stash JSON in entries marked
      // data_type='text'. Opportunistically reparse so the UI can pretty-
      // print them instead of rendering raw braces inline.
      const trimmed = entry.value.trim();
      if (
        (trimmed.startsWith('{') && trimmed.endsWith('}')) ||
        (trimmed.startsWith('[') && trimmed.endsWith(']'))
      ) {
        try {
          const parsed: unknown = JSON.parse(trimmed);
          if (parsed !== null && typeof parsed === 'object') {
            processed.value = parsed;
          }
        } catch {
          // Not actually JSON — leave as the original string.
        }
      }
    }
    return processed;
  });
}

const SOURCE_LABELS: Record<string, string> = {
  system_generated: 'system',
};

function shortSource(source: string): string {
  return SOURCE_LABELS[source] ?? source;
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
    <ScrollArea className="mt-4 w-full overflow-y-auto lg:ml-6 lg:mt-0 lg:max-h-[calc(100vh-180px)] lg:w-1/2">
      <div className="divide-y divide-border pr-3">
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
          const stringValue = !isObject ? String(entry.value) : '';
          const isLongString =
            !isObject && (stringValue.length > 120 || stringValue.includes('\n'));

          // Long markdown values and structured objects share the same block
          // layout: key + source/copy on top, content full-width below.
          if (isObject || isLongString) {
            return (
              <div key={entry.key} className="py-3">
                <FieldHeader label={entry.key} source={entry.source} copyText={copyText} />
                {isObject ? (
                  isValidOCRDataStructure(entry.value) ? (
                    <OCRTable ocrData={entry.value} />
                  ) : (
                    <pre className="overflow-x-auto whitespace-pre-wrap break-words rounded-md bg-secondary p-3 font-mono text-[11.5px] leading-relaxed text-foreground">
                      {JSON.stringify(entry.value, null, 2)}
                    </pre>
                  )
                ) : (
                  <BlockMarkdown text={stringValue} />
                )}
              </div>
            );
          }

          return (
            <Row key={entry.key} label={entry.key} source={entry.source} copyText={copyText}>
              <span className="text-sm text-foreground">{stringValue}</span>
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
    <div className="grid grid-cols-[100px_1fr_auto] items-baseline gap-3 py-3 sm:grid-cols-[128px_1fr_auto]">
      <span className="break-all font-mono text-[11px] uppercase leading-tight tracking-[0.08em] text-muted-foreground">
        {label}
      </span>
      <div className="min-w-0">{children}</div>
      <div className="flex shrink-0 items-center gap-2">
        {source && <SourcePill source={source} />}
        {copyText !== undefined && <CopyToClipboard text={copyText} />}
      </div>
    </div>
  );
}

function FieldHeader({
  label,
  source,
  copyText,
}: {
  label: string;
  source?: string;
  copyText?: string;
}) {
  return (
    <div className="mb-2 flex items-center justify-between gap-3">
      <span className="break-all font-mono text-[11px] uppercase tracking-[0.08em] text-muted-foreground">
        {label}
      </span>
      <div className="flex shrink-0 items-center gap-2">
        {source && <SourcePill source={source} />}
        {copyText !== undefined && <CopyToClipboard text={copyText} />}
      </div>
    </div>
  );
}

function BlockMarkdown({ text }: { text: string }) {
  return (
    <div className="rounded-md border border-border bg-secondary/50 p-3 text-[12px] leading-relaxed">
      <div className="prose prose-sm max-w-none break-words text-foreground prose-p:my-1.5 prose-p:leading-relaxed prose-li:my-0">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
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
  const label = shortSource(source);
  return (
    <span
      className="rounded-sm border border-border px-1.5 py-px font-mono text-[9.5px] uppercase tracking-[0.08em] text-muted-foreground"
      title={source}
    >
      {label}
    </span>
  );
}
