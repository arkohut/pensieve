import type { ReactNode } from 'react';
import { cn } from '$/lib/utils';

export const STAGE_WIDTH = 1280;
export const STAGE_HEIGHT = 720;

/**
 * Fixed-size brand canvas for one promo scene. Fixed dimensions (not responsive)
 * give deterministic screenshots and map cleanly to a future 1080p Remotion frame.
 */
export function Stage({
  children,
  caption,
  className,
}: {
  children: ReactNode;
  caption?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn('relative flex flex-col items-center overflow-hidden bg-background', className)}
      style={{ width: STAGE_WIDTH, height: STAGE_HEIGHT }}
    >
      <div
        className="pointer-events-none absolute inset-0 bg-gradient-to-b from-transparent to-brand/5"
        aria-hidden
      />
      <div className="relative flex flex-1 items-center justify-center">{children}</div>
      {caption && (
        <div className="relative flex items-center gap-3 pb-12">{caption}</div>
      )}
    </div>
  );
}
