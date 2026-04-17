import { lazy, Suspense, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '$/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from '$/components/ui/dropdown-menu';

const LazyCalendar = lazy(() =>
  import('$/components/ui/calendar').then((module) => ({ default: module.Calendar })),
);

type Preset = 'unlimited' | 'threeHours' | 'today' | 'week' | 'month' | 'threeMonths' | 'custom';

interface Props {
  start?: number;
  end?: number;
  onChange: (range: { start?: number; end?: number }) => void;
}

const HOUR = 60 * 60;
const DAY = 24 * HOUR;

function formatDateLabel(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function presetSeconds(p: Preset, nowSec: number): { start?: number; end?: number } {
  switch (p) {
    case 'unlimited':
      return {};
    case 'threeHours':
      return { start: nowSec - 3 * HOUR, end: nowSec };
    case 'today':
      return { start: nowSec - DAY, end: nowSec };
    case 'week':
      return { start: nowSec - 7 * DAY, end: nowSec };
    case 'month':
      return { start: nowSec - 30 * DAY, end: nowSec };
    case 'threeMonths':
      return { start: nowSec - 90 * DAY, end: nowSec };
    case 'custom':
      return {};
  }
}

export function TimeFilter({ start, end, onChange }: Props) {
  const { t } = useTranslation();
  const [preset, setPreset] = useState<Preset>(start || end ? 'custom' : 'unlimited');
  const [customRange, setCustomRange] = useState<{ from?: Date; to?: Date }>({
    from: start ? new Date(start * 1000) : undefined,
    to: end ? new Date(end * 1000) : undefined,
  });

  function pickPreset(p: Preset) {
    setPreset(p);
    if (p !== 'custom') {
      setCustomRange({ from: undefined, to: undefined });
      const nowSec = Math.floor(Date.now() / 1000);
      onChange(presetSeconds(p, nowSec));
    }
  }

  function applyCustom(range: { from?: Date; to?: Date } | undefined) {
    const next = range ?? { from: undefined, to: undefined };
    setCustomRange(next);
    if (preset !== 'custom') setPreset('custom');
    onChange({
      start: next.from ? Math.floor(next.from.getTime() / 1000) : undefined,
      end: next.to ? Math.floor(next.to.getTime() / 1000) : undefined,
    });
  }

  const label = useMemo(() => {
    if (preset === 'custom' && customRange.from && customRange.to) {
      return t('timeFilter.customRange', {
        start: formatDateLabel(customRange.from),
        end: formatDateLabel(customRange.to),
      });
    }
    return t(`timeFilter.${preset}`);
  }, [preset, customRange, t]);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="border p-2 text-xs font-medium focus:outline-none"
        >
          <span className="truncate">{label}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-56" align="start" side="bottom">
        <DropdownMenuLabel>{t('timeFilter.label')}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuRadioGroup value={preset} onValueChange={(v) => pickPreset(v as Preset)}>
          <DropdownMenuRadioItem value="unlimited">
            {t('timeFilter.unlimited')}
          </DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="threeHours">
            {t('timeFilter.threeHours')}
          </DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="today">{t('timeFilter.today')}</DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="week">{t('timeFilter.week')}</DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="month">{t('timeFilter.month')}</DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="threeMonths">
            {t('timeFilter.threeMonths')}
          </DropdownMenuRadioItem>
          <DropdownMenuSub>
            <DropdownMenuSubTrigger>{t('timeFilter.custom')}</DropdownMenuSubTrigger>
            <DropdownMenuSubContent>
              <Suspense
                fallback={<div className="p-3 text-sm text-muted-foreground">{t('loading')}</div>}
              >
                <LazyCalendar
                  mode="range"
                  selected={customRange as never}
                  onSelect={(r) => applyCustom(r as { from?: Date; to?: Date })}
                  numberOfMonths={1}
                />
              </Suspense>
            </DropdownMenuSubContent>
          </DropdownMenuSub>
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
