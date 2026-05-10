import { useState } from 'react';
import { cn } from '$/lib/utils';

interface OCRRow {
  dt_boxes: unknown;
  rec_txt: string;
  score: number;
}

interface Props {
  ocrData: OCRRow[];
}

type Mode = 'text' | 'table';

export function OCRTable({ ocrData }: Props) {
  const [mode, setMode] = useState<Mode>('text');

  if (ocrData.length === 0) {
    return (
      <p className="font-mono text-[11px] text-muted-foreground">No text detected.</p>
    );
  }

  const avgScore =
    ocrData.reduce((acc, r) => acc + r.score, 0) / ocrData.length;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground">
        <span>
          {ocrData.length} regions
          <span className="mx-1.5 opacity-50">·</span>
          avg {avgScore.toFixed(2)}
        </span>
        <ModeToggle mode={mode} onChange={setMode} />
      </div>
      {mode === 'text' ? (
        <div className="max-h-80 overflow-y-auto rounded-md border border-border bg-secondary/50 p-3 font-mono text-[11.5px] leading-relaxed text-foreground">
          <p className="whitespace-pre-wrap break-words">
            {ocrData.map((r) => r.rec_txt).join('\n')}
          </p>
        </div>
      ) : (
        <div className="max-h-80 overflow-auto rounded-md border border-border">
          <table className="w-full table-auto font-mono text-[11px]">
            <thead className="sticky top-0 bg-secondary text-[9.5px] uppercase tracking-[0.08em] text-muted-foreground">
              <tr>
                <th className="px-2.5 py-1 text-left font-medium">Text</th>
                <th className="w-14 px-2.5 py-1 text-right font-medium">Score</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {ocrData.map((row, i) => (
                <tr key={i} className="hover:bg-secondary/40">
                  <td className="px-2.5 py-0.5 align-top text-foreground">
                    <span className="break-all">{row.rec_txt}</span>
                  </td>
                  <td className="px-2.5 py-0.5 text-right tabular-nums text-muted-foreground">
                    {row.score.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ModeToggle({ mode, onChange }: { mode: Mode; onChange: (m: Mode) => void }) {
  return (
    <div className="inline-flex rounded-sm border border-border bg-secondary p-px text-[10px] font-mono uppercase tracking-[0.08em]">
      {(['text', 'table'] as const).map((m) => (
        <button
          key={m}
          type="button"
          onClick={() => onChange(m)}
          className={cn(
            'rounded-[2px] px-2 py-0.5 transition-colors',
            mode === m
              ? 'bg-background text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground',
          )}
        >
          {m}
        </button>
      ))}
    </div>
  );
}

export function isValidOCRDataStructure(data: unknown): data is OCRRow[] {
  if (!Array.isArray(data)) return false;
  for (const item of data) {
    if (
      typeof item !== 'object' ||
      item === null ||
      !('dt_boxes' in item) ||
      !('rec_txt' in item) ||
      !('score' in item)
    ) {
      return false;
    }
    if (
      !Array.isArray((item as OCRRow).dt_boxes) ||
      typeof (item as OCRRow).rec_txt !== 'string' ||
      typeof (item as OCRRow).score !== 'number'
    ) {
      return false;
    }
  }
  return true;
}
