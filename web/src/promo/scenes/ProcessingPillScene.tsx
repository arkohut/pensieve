import { PanelBody, PillButton } from '$/components/common/ProcessingStatusPill';
import { Stage } from '../components/Stage';
import { STATUSES } from './fixtures';

export function ProcessingPillScene() {
  const status = STATUSES[1]; // Processing · 92.1% · 813 backlog

  return (
    <Stage
      caption={
        <span className="font-display text-lg text-foreground">
          Processing status, at a glance.
        </span>
      }
    >
      {/* One whole card: a header row with the real pill, then the real panel body —
          a single border/surface, no nested inner card. */}
      <div className="w-[360px] overflow-hidden rounded-2xl border border-border bg-popover text-popover-foreground shadow-2xl">
        <div className="flex items-center justify-between border-b border-border/70 px-4 py-3">
          <span className="text-xs font-medium text-muted-foreground">Pensieve</span>
          <PillButton status={status} />
        </div>
        <PanelBody status={status} />
      </div>
    </Stage>
  );
}
