// Mock "screenshot" of YouTube. Hardcoded colors. Fills 1280×800.
function PlayTriangle({ className }: { className?: string }) {
  return (
    <span
      className={className}
      style={{
        width: 0,
        height: 0,
        borderTop: '12px solid transparent',
        borderBottom: '12px solid transparent',
        borderLeft: '20px solid white',
      }}
    />
  );
}

export function YouTubeScreen() {
  return (
    <div className="flex h-full w-full flex-col bg-white text-[17px] text-zinc-900">
      {/* top bar */}
      <div className="flex items-center gap-4 px-7 py-4">
        <div className="flex items-center gap-1.5">
          <span className="flex h-7 w-10 items-center justify-center rounded bg-[#ff0000]">
            <span
              style={{
                width: 0,
                height: 0,
                borderTop: '6px solid transparent',
                borderBottom: '6px solid transparent',
                borderLeft: '10px solid white',
                marginLeft: 2,
              }}
            />
          </span>
          <span className="text-[20px] font-semibold tracking-tight">YouTube</span>
        </div>
        <div className="mx-auto flex h-10 w-1/2 items-center rounded-full border border-zinc-300 px-5 text-zinc-400">
          Search
        </div>
        <div className="h-9 w-9 rounded-full bg-gradient-to-br from-orange-400 to-pink-500" />
      </div>
      {/* main */}
      <div className="flex flex-1 gap-6 px-7 pb-7">
        <div className="flex-1">
          <div className="relative aspect-video w-full overflow-hidden rounded-xl bg-zinc-900">
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="flex h-16 w-16 items-center justify-center rounded-full bg-[#ff0000]/90">
                <PlayTriangle className="ml-1" />
              </span>
            </div>
            <div className="absolute bottom-0 left-0 h-1.5 w-2/3 bg-[#ff0000]" />
          </div>
          <div className="mt-4 text-[23px] font-semibold leading-snug">
            Building local-first screenshot search with Pensieve
          </div>
          <div className="mt-3 flex items-center gap-3">
            <div className="h-10 w-10 rounded-full bg-gradient-to-br from-orange-400 to-pink-500" />
            <div className="leading-tight">
              <div className="font-medium">Pensieve</div>
              <div className="text-[14px] text-zinc-500">128K subscribers</div>
            </div>
            <span className="ml-3 rounded-full bg-zinc-900 px-5 py-2 text-[15px] font-medium text-white">
              Subscribe
            </span>
          </div>
        </div>
        {/* sidebar */}
        <div className="w-80 space-y-3.5">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="flex gap-3">
              <div className="h-20 w-32 shrink-0 rounded-lg bg-zinc-200" />
              <div className="space-y-2 pt-1">
                <div className="h-3 w-40 rounded bg-zinc-300" />
                <div className="h-3 w-24 rounded bg-zinc-200" />
                <div className="h-3 w-16 rounded bg-zinc-100" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
