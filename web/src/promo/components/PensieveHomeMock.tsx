import type { ReactNode } from 'react';
import { Globe, Moon, Search, Settings } from 'lucide-react';
import { Logo } from '$/components/common/Logo';
import { TILES } from '../assets/tiles';

/** Faithful-enough Pensieve home: header (with a live pill slot) + hero + search + tile grid. */
export function PensieveHomeMock({ pill }: { pill: ReactNode }) {
  return (
    <div className="flex h-full w-full flex-col bg-background text-foreground">
      <header className="flex items-center justify-between border-b border-border px-6 py-3">
        <Logo size={26} withBorder={false} />
        <div className="flex items-center gap-3 text-muted-foreground">
          {pill}
          <Globe size={16} />
          <Moon size={16} />
          <Settings size={16} />
        </div>
      </header>
      <div className="flex-1 px-8 py-6">
        <h2 className="font-display text-2xl font-normal tracking-tight">
          Record, Retrieve, Review.
        </h2>
        <p className="mt-1 text-[11px] tabular-nums text-muted-foreground">1,488,618 screens indexed.</p>
        <div className="mt-4 flex items-center gap-2 rounded-md border border-border px-3 py-2 text-xs text-muted-foreground">
          <Search size={14} />
          <span>Input keyword to search or press Enter to show latest records</span>
        </div>
        <div className="mt-5 grid grid-cols-4 gap-3">
          {TILES.map((src, i) => (
            <div key={i} className="overflow-hidden rounded-md border border-border">
              <img src={src} alt="" className="h-20 w-full object-cover" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
