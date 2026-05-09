import { useTranslation } from 'react-i18next';
import { cn } from '$/lib/utils';
import type { DateBucket } from '$/lib/api/types';

interface Props {
  buckets: DateBucket[];
  unit: 'day' | 'month';
  selected?: string;
  onToggle: (date: string | undefined) => void;
}

function formatLabel(bucket: string, unit: 'day' | 'month'): string {
  // bucket is 'YYYY-MM' (month) or 'YYYY-MM-DD' (day) — render in user locale
  const d = new Date(`${bucket}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return bucket;
  if (unit === 'month') {
    return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', timeZone: 'UTC' });
  }
  return d.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  });
}

export function DateBucketFilter({ buckets, unit, selected, onToggle }: Props) {
  const { t } = useTranslation();
  // When drilling into a month, show its name in the heading so the user
  // always knows which scope the day buckets belong to — even when the
  // selected day isn't in the current bucket list (e.g. just-clicked month).
  const scopeMonth = selected?.slice(0, 7);
  const heading =
    unit === 'day' && scopeMonth
      ? t('search.dateBucketsDayInScope', { scope: formatLabel(scopeMonth, 'month') })
      : unit === 'month'
        ? t('search.dateBucketsMonth')
        : t('search.dateBucketsDay');

  return (
    <div className="mb-4">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-lg font-semibold">{heading}</h3>
        {selected && (
          <button
            type="button"
            onClick={() => onToggle(undefined)}
            className="text-xs text-muted-foreground hover:text-foreground hover:underline"
          >
            {t('search.clearDate')}
          </button>
        )}
      </div>
      {buckets.map((b) => {
        const isSelected = selected === b.date;
        return (
          <button
            key={b.date}
            type="button"
            onClick={() => onToggle(isSelected ? undefined : b.date)}
            className={cn(
              'mb-1 block w-full rounded px-2 py-1 text-left text-sm transition-colors',
              'hover:bg-accent hover:text-accent-foreground',
              isSelected && 'bg-accent font-medium text-accent-foreground',
            )}
          >
            {formatLabel(b.date, unit)} ({b.count})
          </button>
        );
      })}
    </div>
  );
}
