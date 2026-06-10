import { Search } from 'lucide-react';
import { HitCard } from '$/components/search/HitCard';
import type { Hit } from '$/lib/api/types';
import { Stage } from '../components/Stage';

const NOW = Date.now();

// One scene file = real component + fixtures. HitCard pulls its thumbnail from
// `<origin>/api/thumbnails/<filepath>`, served here from src/promo/public/.
function hit(opts: {
  filepath: string;
  title: string;
  app: string;
  screen?: string;
  agoSec: number;
}): Hit {
  const at = new Date(NOW - opts.agoSec * 1000).toISOString();
  return {
    document: {
      id: 1,
      library_id: 1,
      folder_id: 1,
      filepath: opts.filepath,
      filename: opts.filepath,
      file_created_at: at,
      file_last_modified_at: at,
      tags: [],
      metadata_entries: [
        { key: 'active_window', source: 'watch', value: opts.title },
        { key: 'active_app', source: 'watch', value: opts.app },
        ...(opts.screen ? [{ key: 'screen_name', source: 'watch', value: opts.screen }] : []),
      ],
    },
  };
}

const HITS: Hit[] = [
  hit({ filepath: 'shot-1.jpeg', title: 'Mastra integration — agents & workflows', app: 'chrome', agoSec: 16 }),
  hit({ filepath: 'shot-2.jpeg', title: 'Pensieve promo deck', app: 'figma', screen: 'studio display', agoSec: 43 }),
  hit({ filepath: 'shot-3.jpeg', title: 'Processing-status pill review', app: 'code', agoSec: 54 }),
];

export function SearchScene() {
  return (
    <Stage
      caption={
        <span className="font-display text-lg text-foreground">
          Search your entire screen history.
        </span>
      }
    >
      {/* One complete search surface: a query bar + the real HitCard results. */}
      <div className="w-[880px] overflow-hidden rounded-2xl border border-border bg-card shadow-2xl">
        <div className="border-b border-border px-6 py-4">
          <div className="flex items-center gap-2.5 rounded-lg border border-border bg-background px-4 py-2.5">
            <Search size={16} className="text-muted-foreground" />
            <span className="text-sm text-foreground">mastra integration</span>
            <span className="ml-auto font-mono text-[11px] tabular-nums text-muted-foreground">
              233,860 matches
            </span>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-5 p-6">
          {HITS.map((h, i) => (
            <HitCard key={i} hit={h} onClick={() => {}} />
          ))}
        </div>
      </div>
    </Stage>
  );
}
