import { useMemo } from 'react';
import { generateLogo } from '$/lib/logo-generator';
import { cn } from '$/lib/utils';

interface Props {
  size?: number;
  className?: string;
  withBorder?: boolean;
  hasGap?: boolean;
}

export function Logo({ size = 32, className, withBorder = true, hasGap = true }: Props) {
  const svg = useMemo(
    () => generateLogo(size, withBorder, hasGap),
    [size, withBorder, hasGap],
  );
  return <div className={cn(className)} dangerouslySetInnerHTML={{ __html: svg }} />;
}
