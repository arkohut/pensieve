import type { CSSProperties, ReactNode } from 'react';

export interface CalloutLine {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

/**
 * Fixed-anchor annotation: a dashed line from (x1,y1) to (x2,y2) plus a bubble
 * positioned via `style`. Both are absolutely placed relative to the scene's
 * positioned wrapper, so the scene owns the exact coordinates.
 */
export function Callout({
  children,
  style,
  line,
}: {
  children: ReactNode;
  style?: CSSProperties;
  line?: CalloutLine;
}) {
  return (
    <>
      {line && (
        <svg className="pointer-events-none absolute inset-0 h-full w-full overflow-visible" aria-hidden>
          <line
            x1={line.x1}
            y1={line.y1}
            x2={line.x2}
            y2={line.y2}
            className="stroke-border"
            strokeWidth={1.5}
            strokeDasharray="4 3"
          />
          <circle cx={line.x1} cy={line.y1} r={3} className="fill-brand" />
        </svg>
      )}
      <div className="absolute" style={style}>
        {children}
      </div>
    </>
  );
}
