import type { ReactNode } from 'react';
import { LucideIcon } from '$/components/common/LucideIcon';
import { cn, translateAppName, filename } from '$/lib/utils';
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

function getScreenName(doc: Hit['document']): string | null {
  const sn = doc.metadata_entries?.find((e) => e.key === 'screen_name');
  return sn?.value ?? null;
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
  /** Total frames represented by this card; >= 2 renders a stack with a count badge. */
  stackCount?: number;
  onClick: () => void;
  /** Optional thumbnail override (e.g. a rendered mock screen for promo shots). */
  thumbnail?: ReactNode;
}

export function HitCard({ hit, stackCount = 1, onClick, thumbnail }: Props) {
  const title = getEntityTitle(hit.document);
  const appName = getAppName(hit.document);
  const screenName = getScreenName(hit.document);
  const iconName = translateAppName(appName) ?? 'Hexagon';
  const subtitle = [appName !== 'unknown' ? appName : null, screenName]
    .filter(Boolean)
    .join(' · ');

  // Two underlay panels read enough as "a few"; three look like a real pile.
  const stackClass = stackCount >= 4 ? 'stack-3' : stackCount >= 2 ? 'stack-2' : null;

  return (
    <button
      type="button"
      onClick={onClick}
      className="group block w-full text-left transition-transform duration-200 ease-out hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
    >
      <div className={cn('relative', stackClass)}>
        <figure className={cn(
          'aspect-[16/10] overflow-hidden rounded-md border border-border bg-secondary transition-shadow duration-200 group-hover:shadow-[0_8px_24px_-8px_rgba(0,0,0,0.18)]',
          stackClass && 'stack-top',
        )}>
          {thumbnail ?? (
            <img
              loading="lazy"
              decoding="async"
              className="h-full w-full object-cover"
              src={`${apiEndpoint}/thumbnails/${hit.document.filepath.replace(/^\/+/, '')}`}
              alt=""
            />
          )}
        </figure>
        {stackCount >= 2 && (
          <span
            className="absolute right-2 top-2 z-[3] inline-flex items-center rounded-full bg-foreground/85 px-2 py-0.5 font-mono text-[10px] font-medium tracking-wide text-background backdrop-blur-sm"
            aria-label={`${stackCount} similar frames`}
          >
            ×&nbsp;{stackCount}
          </span>
        )}
      </div>
      <div className="mt-2.5 flex items-baseline gap-3">
        <h2 className="min-w-0 flex-1 truncate text-[13px] font-medium leading-tight text-foreground">
          {title}
        </h2>
        <span className="shrink-0 font-mono text-[11px] tracking-wide text-muted-foreground">
          {formatRelativeTime(hit.document.file_created_at)}
        </span>
      </div>
      {subtitle && (
        <p className="mt-1 flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
          <LucideIcon name={iconName} size={12} className="shrink-0 opacity-70" />
          <span className="truncate">{subtitle}</span>
        </p>
      )}
    </button>
  );
}
