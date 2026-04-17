import { LucideIcon } from '$/components/common/LucideIcon';
import { translateAppName, filename } from '$/lib/utils';
import type { Hit } from '$/lib/api/types';
import { apiEndpoint } from '$/lib/api/client';

function getEntityTitle(doc: Hit['document']): string {
  const aw = doc.metadata_entries?.find((e) => e.key === 'active_window');
  if (aw) return aw.value;
  return filename(doc.filepath);
}

function getAppName(doc: Hit['document']): string {
  const aa = doc.metadata_entries?.find((e) => e.key === 'active_app');
  return aa?.value ?? 'unknown';
}

const RELATIVE_TIME_DIVISIONS = [
  { amount: 60, unit: 'second' },
  { amount: 60, unit: 'minute' },
  { amount: 24, unit: 'hour' },
  { amount: 7, unit: 'day' },
  { amount: 4.34524, unit: 'week' },
  { amount: 12, unit: 'month' },
  { amount: Number.POSITIVE_INFINITY, unit: 'year' },
] as const;

function formatRelativeTime(value: string): string {
  const date = new Date(value);
  const time = date.getTime();

  if (Number.isNaN(time)) return value;

  let duration = Math.round((time - Date.now()) / 1000);
  for (const division of RELATIVE_TIME_DIVISIONS) {
    if (Math.abs(duration) < division.amount) {
      return new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' }).format(
        Math.round(duration),
        division.unit,
      );
    }
    duration /= division.amount;
  }

  return value;
}

interface Props {
  hit: Hit;
  onClick: () => void;
}

export function HitCard({ hit, onClick }: Props) {
  const title = getEntityTitle(hit.document);
  const appName = getAppName(hit.document);
  const iconName = translateAppName(appName) ?? 'Hexagon';

  return (
    <button
      type="button"
      onClick={onClick}
      className="relative overflow-hidden rounded-lg border bg-card text-left hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <div className="px-4 pt-4">
        <h2 className="line-clamp-2 h-12">{title}</h2>
        <p className="text-xs text-muted-foreground">{formatRelativeTime(hit.document.file_created_at)}</p>
      </div>
      <figure className="relative mb-4 px-4 pt-4">
        <img
          loading="lazy"
          decoding="async"
          className="h-48 w-full object-cover"
          src={`${apiEndpoint}/thumbnails/${hit.document.filepath.replace(/^\/+/, '')}`}
          alt=""
        />
        {appName !== 'unknown' && (
          <div className="absolute bottom-2 left-6 flex items-center space-x-2 rounded-full border bg-card/75 px-2 py-1 text-xs font-semibold">
            <LucideIcon name={iconName} size={16} />
            <span>{appName}</span>
          </div>
        )}
      </figure>
    </button>
  );
}
