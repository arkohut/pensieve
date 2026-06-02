import { Settings } from 'lucide-react';
import { Button } from '$/components/ui/button';
import { LanguageSwitcher } from '$/components/common/LanguageSwitcher';
import { Logo } from '$/components/common/Logo';
import { PageHeader } from '$/components/common/PageHeader';
import { ThemeToggle } from '$/components/common/ThemeToggle';
import { PillStandalone, PanelStandalone } from './showcase/StatusShowcase';
import { STATUSES, STATE_LABELS } from './showcase/statuses';

export function ChipPromo() {
  return (
    <div className="flex min-h-screen flex-col">
      <PageHeader
        maxWidth="max-w-screen-xl"
        left={
          <div className="flex items-center">
            <Logo size={40} withBorder={false} />
          </div>
        }
        right={
          <div className="flex items-center gap-1">
            <PillStandalone status={STATUSES[0]} />
            <LanguageSwitcher />
            <ThemeToggle />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-muted-foreground hover:text-foreground"
              title="Settings"
            >
              <Settings size={18} />
            </Button>
          </div>
        }
      />

      <div className="mx-auto w-full px-6 pb-16 pt-12">
        <div className="text-center">
          <div className="mb-3 inline-flex items-center gap-3 font-mono text-[11px] uppercase tracking-[0.28em] text-muted-foreground">
            <span className="h-px w-8 bg-border" />
            Pensieve · New in v0.37.0
            <span className="h-px w-8 bg-border" />
          </div>
          <h1 className="font-display text-5xl font-normal leading-tight tracking-tight text-foreground sm:text-[64px]">
            Processing Status, <span className="text-brand">at a glance</span>.
          </h1>
          <p className="mx-auto mt-3 max-w-2xl text-[15px] leading-relaxed text-muted-foreground">
            A tiny chip in the navigation header tells you exactly where your screenshot ingestion
            stands. One dot. Four states. Click for the details.
          </p>
        </div>

        <div className="mt-10 flex items-start justify-center gap-10">
          {STATUSES.map((s, i) => (
            <div key={i} className="flex flex-col items-center gap-3.5">
              <PillStandalone status={s} />
              <div className="h-3.5 w-px bg-border" />
              <PanelStandalone status={s} />
            </div>
          ))}
        </div>

        <div className="mt-4 flex justify-center gap-10">
          {STATE_LABELS.map((t, i) => (
            <div
              key={i}
              className="w-80 text-center font-mono text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground"
            >
              {t}
            </div>
          ))}
        </div>

        <div className="mt-12 text-center font-mono text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground">
          v0.37.0 · /api/libraries/{'{id}'}/processing-status
        </div>
      </div>
    </div>
  );
}
