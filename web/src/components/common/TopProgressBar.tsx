import { useEffect, useState } from 'react';
import { useIsFetching } from '@tanstack/react-query';
import { cn } from '$/lib/utils';

/**
 * Indeterminate top progress bar driven by react-query's global fetching count.
 * Shows whenever any query is in flight; fades out smoothly on completion so
 * fast queries don't flash.
 */
export function TopProgressBar() {
  const fetching = useIsFetching();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (fetching > 0) {
      setVisible(true);
      return;
    }
    const t = setTimeout(() => setVisible(false), 200);
    return () => clearTimeout(t);
  }, [fetching]);

  return (
    <div
      aria-hidden
      className={cn(
        'pointer-events-none fixed inset-x-0 top-0 z-50 h-0.5 overflow-hidden transition-opacity duration-200',
        visible ? 'opacity-100' : 'opacity-0',
      )}
    >
      <div className="h-full w-1/4 animate-progress-slide bg-primary" />
    </div>
  );
}
