import type { ReactNode } from 'react';
import { cn } from '$/lib/utils';

/** Browser frame mock: traffic lights + address bar. Body region renders children. */
export function BrowserChrome({
  url,
  children,
  className,
}: {
  url: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        'overflow-hidden rounded-xl border border-border bg-card shadow-2xl',
        className,
      )}
    >
      <div className="flex h-10 items-center gap-3 border-b border-border bg-muted/40 px-4">
        <div className="flex gap-2">
          <span className="h-3 w-3 rounded-full bg-red-400" />
          <span className="h-3 w-3 rounded-full bg-amber-400" />
          <span className="h-3 w-3 rounded-full bg-emerald-400" />
        </div>
        <div className="ml-2 flex h-6 flex-1 items-center rounded-md bg-background px-3 text-[11px] text-muted-foreground">
          {url}
        </div>
      </div>
      <div className="relative">{children}</div>
    </div>
  );
}
