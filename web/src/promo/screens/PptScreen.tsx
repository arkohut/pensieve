import { cn } from '$/lib/utils';

// Mock "screenshot" of a slides editor (PowerPoint-like). Hardcoded colors. Fills 1280×800.
export function PptScreen() {
  return (
    <div className="flex h-full w-full flex-col bg-[#f3f3f3] text-zinc-800">
      <div className="flex items-center gap-5 bg-[#b7472a] px-6 py-3 text-[16px] text-white">
        <span className="font-semibold">PowerPoint</span>
        <span className="opacity-85">Home</span>
        <span className="opacity-85">Insert</span>
        <span className="opacity-85">Design</span>
        <span className="ml-auto opacity-90">▷ Present</span>
      </div>
      <div className="flex flex-1 overflow-hidden">
        <div className="w-52 space-y-3 overflow-hidden bg-[#ededed] p-4">
          {[1, 2, 3, 4].map((n) => (
            <div key={n} className="flex gap-2">
              <span className="w-4 text-[13px] text-zinc-500">{n}</span>
              <div className={cn('aspect-video flex-1 rounded bg-white', n === 1 ? 'border-2 border-[#b7472a]' : 'border border-zinc-300')}>
                <div className="p-2">
                  <div className="h-2 w-2/3 rounded bg-zinc-300" />
                  <div className="mt-1.5 h-1.5 w-1/2 rounded bg-zinc-200" />
                </div>
              </div>
            </div>
          ))}
        </div>
        <div className="flex flex-1 items-center justify-center bg-[#d9d9d9] p-10">
          <div className="aspect-video w-full max-w-3xl rounded-lg bg-white p-12 shadow-xl">
            <div className="text-[40px] font-bold text-zinc-900">Pensieve</div>
            <div className="mt-1 text-[20px] text-[#b7472a]">Your screen, searchable.</div>
            <div className="mt-8 space-y-4 text-[22px] text-zinc-700">
              <div className="flex items-center gap-3"><span className="h-2.5 w-2.5 rounded-full bg-[#b7472a]" /> Records everything you see</div>
              <div className="flex items-center gap-3"><span className="h-2.5 w-2.5 rounded-full bg-[#b7472a]" /> Search by text, app, or time</div>
              <div className="flex items-center gap-3"><span className="h-2.5 w-2.5 rounded-full bg-[#b7472a]" /> Fully local &amp; private</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
