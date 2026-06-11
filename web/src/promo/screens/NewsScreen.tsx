// Mock "screenshot" of a news article. Hardcoded colors. Fills 1280×800.
export function NewsScreen() {
  return (
    <div className="flex h-full w-full flex-col bg-[#fbfbf9] px-20 py-12 text-zinc-900">
      <div className="border-b border-zinc-300 pb-5 text-center">
        <div className="font-serif text-[36px] font-bold tracking-tight">The Daily Ledger</div>
        <div className="mt-1.5 text-[13px] uppercase tracking-[0.3em] text-zinc-500">
          Technology · Tuesday
        </div>
      </div>
      <div className="mt-8 font-serif text-[44px] font-bold leading-tight">
        Local-first apps are quietly winning back our data
      </div>
      <div className="mt-3 text-[16px] text-zinc-500">By A. Reporter · 6 min read</div>
      <div className="mt-6 aspect-[16/6] w-full rounded bg-gradient-to-br from-zinc-300 to-zinc-200" />
      <div className="mt-7 grid grid-cols-2 gap-10">
        {[0, 1].map((c) => (
          <div key={c} className="space-y-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="h-3.5 rounded bg-zinc-300"
                style={{ width: `${78 + ((i * 11 + c * 5) % 22)}%` }}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
