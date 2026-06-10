import type { ComponentType } from 'react';
import { Globe, Moon, Search, Settings } from 'lucide-react';
import { Logo } from '$/components/common/Logo';
import { PillButton } from '$/components/common/ProcessingStatusPill';
import { FacetFilter } from '$/components/search/FacetFilter';
import { HitCard } from '$/components/search/HitCard';
import type { Facet, Hit } from '$/lib/api/types';
import { Stage } from '../components/Stage';
import { ScreenBox } from '../screens/ScreenBox';
import { DocsScreen } from '../screens/DocsScreen';
import { GmailScreen } from '../screens/GmailScreen';
import { IdeScreen } from '../screens/IdeScreen';
import { NewsScreen } from '../screens/NewsScreen';
import { PptScreen } from '../screens/PptScreen';
import { TerminalScreen } from '../screens/TerminalScreen';
import { TwitterScreen } from '../screens/TwitterScreen';
import { WechatScreen } from '../screens/WechatScreen';
import { YouTubeScreen } from '../screens/YouTubeScreen';
import { STATUSES } from './fixtures';

const NOW = Date.now();

function hit(opts: { title: string; app: string; screen?: string; agoSec: number }): Hit {
  const at = new Date(NOW - opts.agoSec * 1000).toISOString();
  return {
    document: {
      id: opts.agoSec,
      library_id: 1,
      folder_id: 1,
      filepath: '',
      filename: '',
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

interface Result {
  Screen: ComponentType;
  hit: Hit;
  stack?: number;
}

const RESULTS: Result[] = [
  { Screen: YouTubeScreen, hit: hit({ title: 'Building local-first screenshot search', app: 'YouTube', agoSec: 16 }), stack: 3 },
  { Screen: TwitterScreen, hit: hit({ title: 'Pensieve — your screen, searchable', app: 'X', agoSec: 43 }) },
  { Screen: NewsScreen, hit: hit({ title: 'Local-first apps are winning back our data', app: 'Safari', agoSec: 134 }) },
  { Screen: GmailScreen, hit: hit({ title: 'Your weekly recap is ready', app: 'Mail', agoSec: 320 }) },
  { Screen: WechatScreen, hit: hit({ title: 'Pensieve 团队 · 单卡那版定了', app: 'WeChat', agoSec: 720 }) },
  { Screen: DocsScreen, hit: hit({ title: 'Pensieve — Product Brief', app: 'Chrome', agoSec: 1500 }) },
  { Screen: PptScreen, hit: hit({ title: 'Pensieve pitch deck', app: 'PowerPoint', screen: 'studio display', agoSec: 2300 }), stack: 5 },
  { Screen: TerminalScreen, hit: hit({ title: 'git status — chip-promo-static-build', app: 'Terminal', agoSec: 3200 }) },
  { Screen: IdeScreen, hit: hit({ title: 'IdeScreen.tsx — promo scene', app: 'Code', agoSec: 3900 }), stack: 2 },
  { Screen: YouTubeScreen, hit: hit({ title: 'Remotion crash course', app: 'YouTube', agoSec: 5400 }) },
  { Screen: WechatScreen, hit: hit({ title: '前端交流群 · 这个截图体系不错', app: 'WeChat', agoSec: 7200 }) },
  { Screen: DocsScreen, hit: hit({ title: 'Release notes — v0.37.0', app: 'Chrome', agoSec: 9100 }) },
];

const APP_FACET: Facet = {
  field_name: 'app_names',
  counts: [
    { value: 'Chrome', count: 84203 },
    { value: 'Code', count: 51877 },
    { value: 'YouTube', count: 22140 },
    { value: 'Safari', count: 18934 },
    { value: 'Figma', count: 12060 },
    { value: 'Terminal', count: 9821 },
    { value: 'WeChat', count: 7415 },
    { value: 'Mail', count: 4302 },
  ],
};
const SELECTED_APPS = ['Chrome', 'Code'];

export function SearchScene() {
  return (
    <Stage
      height={940}
      caption={
        <span className="font-display text-lg text-foreground">
          Search your entire screen history.
        </span>
      }
    >
      {/* A faithful slice of the real search page: real nav + hero + sidebar
          facet filter + the real HitCard grid, with mock app-screens as thumbnails. */}
      <div className="flex h-[820px] w-[1180px] flex-col overflow-hidden rounded-2xl border border-border bg-background shadow-2xl">
        {/* nav */}
        <div className="flex shrink-0 items-center justify-between border-b border-border px-7 py-3">
          <Logo size={30} withBorder={false} />
          <div className="flex items-center gap-3 text-muted-foreground">
            <PillButton status={STATUSES[0]} />
            <Globe size={17} />
            <Moon size={17} />
            <Settings size={17} />
          </div>
        </div>

        {/* hero + (sidebar | results), clipped by the window like a scrolled page */}
        <div className="min-h-0 flex-1 overflow-hidden px-9">
          <h1 className="mt-6 font-display text-[30px] font-normal tracking-tight text-foreground">
            Record, Retrieve, Review.
          </h1>
          <p className="mt-1.5 text-sm text-muted-foreground">
            <span className="font-mono text-[13px] tabular-nums text-brand">1,488,618</span> screens indexed
          </p>

          <div className="mt-5 flex h-11 max-w-2xl items-center gap-2.5 rounded-md border border-border px-3.5 text-[15px]">
            <Search size={16} className="text-muted-foreground" />
            <span className="text-foreground">mastra integration</span>
          </div>
          <div className="mt-3 flex gap-2 text-[13px] text-muted-foreground">
            <span className="rounded-full border border-border px-3 py-1">All libraries</span>
            <span className="rounded-full border border-border px-3 py-1">Last 3 months</span>
          </div>

          <div className="mt-7 flex gap-8">
            <aside className="w-56 shrink-0">
              <FacetFilter facet={APP_FACET} selected={SELECTED_APPS} onToggle={() => {}} />
            </aside>
            <div className="min-w-0 flex-1">
              <div className="mb-5 border-b border-border pb-2.5 font-mono text-[11.5px] uppercase tracking-[0.08em] text-muted-foreground">
                233,860 matches in 1,488,618 screenshots
              </div>
              <div className="grid grid-cols-3 gap-x-5 gap-y-7">
                {RESULTS.map((r, i) => (
                  <HitCard
                    key={i}
                    hit={r.hit}
                    stackCount={r.stack}
                    onClick={() => {}}
                    thumbnail={
                      <ScreenBox width={270}>
                        <r.Screen />
                      </ScreenBox>
                    }
                  />
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </Stage>
  );
}
