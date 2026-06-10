import type { ReactNode } from 'react';

// All mock screens are authored at this logical size, then scaled to fit any box.
export const SCREEN_W = 1280;
export const SCREEN_H = 800;

/** Scales a fixed-size mock screen down (or up) into a `width`-wide box, 16:10. */
export function ScreenBox({
  width,
  children,
  className,
}: {
  width: number;
  children: ReactNode;
  className?: string;
}) {
  const scale = width / SCREEN_W;
  return (
    <div
      className={className}
      style={{ width, height: SCREEN_H * scale, overflow: 'hidden' }}
    >
      <div
        style={{
          width: SCREEN_W,
          height: SCREEN_H,
          transform: `scale(${scale})`,
          transformOrigin: 'top left',
        }}
      >
        {children}
      </div>
    </div>
  );
}
