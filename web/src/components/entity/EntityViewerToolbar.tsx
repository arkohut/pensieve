import { type ReactNode, useMemo } from 'react';
import { Check, Columns2, PanelLeft, PanelRight } from 'lucide-react';
import { Button } from '$/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '$/components/ui/dropdown-menu';
import { LucideIcon } from '$/components/common/LucideIcon';
import { translateAppName, formatDate, filename, cn } from '$/lib/utils';
import type { Entity } from '$/lib/api/types';

export type ViewerLayout = 'both' | 'image' | 'details';

interface Props {
  entity: Entity | null;
  layout: ViewerLayout;
  onLayoutChange: (layout: ViewerLayout) => void;
  leftAction?: ReactNode;
  rightAction?: ReactNode;
}

const LAYOUT_OPTIONS: Array<{ value: ViewerLayout; label: string; Icon: typeof Columns2 }> = [
  { value: 'both', label: 'Image & details', Icon: Columns2 },
  { value: 'image', label: 'Image only', Icon: PanelLeft },
  { value: 'details', label: 'Details only', Icon: PanelRight },
];

function getEntityTitle(doc: Entity): string {
  const aw = doc.metadata_entries?.find((e) => e.key === 'active_window');
  if (aw) return aw.value;
  return doc.filepath ? filename(doc.filepath) : '';
}

function getAppName(doc: Entity): string {
  const aa = doc.metadata_entries?.find((e) => e.key === 'active_app');
  return aa?.value ?? 'unknown';
}

export function EntityViewerToolbar({
  entity,
  layout,
  onLayoutChange,
  leftAction,
  rightAction,
}: Props) {
  const displayTitle = entity ? getEntityTitle(entity) : 'unknown';
  const displayAppName = entity ? getAppName(entity) : 'unknown';
  const formattedCreatedAt = useMemo(
    () => (entity?.file_created_at ? formatDate(entity.file_created_at) : ''),
    [entity?.file_created_at],
  );

  const current = LAYOUT_OPTIONS.find((o) => o.value === layout) ?? LAYOUT_OPTIONS[0];
  const showInlineTime = layout === 'image';

  return (
    <div className="relative z-[52] flex w-full items-center gap-2">
      <div className="flex-none">{leftAction}</div>
      <div className="flex min-w-0 flex-1 items-center justify-center">
        <div className="flex min-w-0 items-center gap-2">
          <LucideIcon name={translateAppName(displayAppName) ?? 'Image'} size={20} />
          <p className="truncate text-base font-medium leading-tight">{displayTitle}</p>
          {showInlineTime && formattedCreatedAt && (
            <span className="ml-3 font-mono text-xs text-muted-foreground">
              {formattedCreatedAt}
            </span>
          )}
        </div>
      </div>
      <div className="flex flex-none items-center gap-1">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-muted-foreground hover:text-foreground"
              aria-label={`Layout: ${current.label}`}
              title={`Layout: ${current.label}`}
            >
              <current.Icon size={18} />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="min-w-[10rem]">
            {LAYOUT_OPTIONS.map(({ value, label, Icon }) => (
              <DropdownMenuItem
                key={value}
                onClick={() => onLayoutChange(value)}
                className="gap-2"
              >
                <Icon size={14} className="text-muted-foreground" />
                <span className="flex-1">{label}</span>
                <Check
                  size={14}
                  className={cn(
                    'text-brand transition-opacity',
                    value === layout ? 'opacity-100' : 'opacity-0',
                  )}
                />
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
        {rightAction}
      </div>
    </div>
  );
}
