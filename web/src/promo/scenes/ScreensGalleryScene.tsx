import { Stage } from '../components/Stage';
import { SCREENS } from '../screens';
import { ScreenBox } from '../screens/ScreenBox';

/** Preview sheet of the reusable mock app-screens (HTML, scalable). */
export function ScreensGalleryScene() {
  return (
    <Stage
      caption={
        <span className="font-display text-lg text-foreground">Mock app screens (HTML, scalable)</span>
      }
    >
      <div className="grid grid-cols-3 gap-x-6 gap-y-4">
        {SCREENS.map((s) => (
          <div key={s.id} className="flex flex-col gap-1.5">
            <div className="overflow-hidden rounded-lg border border-border shadow-md">
              <ScreenBox width={270}>
                <s.Component />
              </ScreenBox>
            </div>
            <span className="text-[11px] text-muted-foreground">{s.label}</span>
          </div>
        ))}
      </div>
    </Stage>
  );
}
