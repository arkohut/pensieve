import type { ReactNode } from 'react';
import { cn } from '$/lib/utils';

interface Props {
  left?: ReactNode;
  right?: ReactNode;
  sticky?: boolean;
  maxWidth?: string;
  className?: string;
}

export function PageHeader({
  left,
  right,
  sticky = false,
  maxWidth = 'max-w-screen-lg',
  className,
}: Props) {
  return (
    <div
      className={cn(
        'w-full border-b bg-background',
        sticky && 'sticky top-0 z-10',
        className,
      )}
    >
      <div
        className={cn(
          'mx-auto flex items-center justify-between gap-2 px-4 py-2',
          maxWidth,
        )}
      >
        <div className="flex items-center gap-2">{left}</div>
        <div className="flex items-center gap-2">{right}</div>
      </div>
    </div>
  );
}
