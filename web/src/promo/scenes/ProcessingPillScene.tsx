import { Logo } from '$/components/common/Logo';
import { BrowserChrome } from '../components/BrowserChrome';
import { Callout } from '../components/Callout';
import { PensieveHomeMock } from '../components/PensieveHomeMock';
import { Stage } from '../components/Stage';
import { PanelStandalone, PillStandalone } from '../showcase/StatusShowcase';
import { STATUSES } from '../showcase/statuses';

export function ProcessingPillScene() {
  const status = STATUSES[1]; // Processing · 92.1% · 813 backlog

  return (
    <Stage
      caption={
        <>
          <span className="font-display text-lg text-foreground">
            Processing status, at a glance.
          </span>
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Logo size={16} withBorder={false} /> Pensieve
          </span>
        </>
      }
    >
      {/* Fixed inner canvas — Callout coords below are in THIS box's space. */}
      <div className="relative" style={{ width: 1040, height: 500 }}>
        <BrowserChrome url="pensieve.app" className="absolute inset-0">
          <div style={{ height: 460 }}>
            <PensieveHomeMock pill={<PillStandalone status={status} />} />
          </div>
        </BrowserChrome>

        <Callout
          style={{ right: 28, top: 104, width: 320 }}
          line={{ x1: 956, y1: 62, x2: 792, y2: 104 }}
        >
          <div className="flex flex-col items-center gap-3">
            <PillStandalone status={status} />
            <PanelStandalone status={status} />
          </div>
        </Callout>
      </div>
    </Stage>
  );
}
