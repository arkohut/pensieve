// Mock "screenshot" of Google Docs. Hardcoded colors. Fills 1280×800.
export function DocsScreen() {
  return (
    <div className="flex h-full w-full flex-col bg-[#f9fbfd] text-zinc-800">
      <div className="flex items-center gap-3 px-6 py-3">
        <span className="flex h-9 w-9 items-center justify-center rounded bg-[#4285f4] text-[18px] text-white">D</span>
        <div className="leading-tight">
          <div className="text-[18px]">Pensieve — Product Brief</div>
          <div className="text-[13px] text-zinc-500">File&nbsp; Edit&nbsp; View&nbsp; Insert&nbsp; Format</div>
        </div>
        <span className="ml-auto rounded-full bg-[#c2e7ff] px-5 py-2 text-[14px] text-[#001d35]">Share</span>
      </div>
      <div className="flex items-center gap-5 bg-[#edf2fa] px-6 py-2 text-[18px] text-zinc-500">
        <span>↶</span>
        <span>↷</span>
        <span className="font-bold">B</span>
        <span className="italic">I</span>
        <span className="underline">U</span>
        <span>≣</span>
      </div>
      <div className="flex flex-1 justify-center overflow-hidden bg-[#f0f3f7] py-8">
        <div className="w-[760px] rounded-sm bg-white px-20 py-14 shadow">
          <div className="text-[34px] font-semibold text-zinc-900">Product Brief</div>
          <div className="mt-2 text-[16px] text-zinc-500">Updated today · A. Reporter</div>
          <div className="mt-7 space-y-3.5">
            {Array.from({ length: 9 }).map((_, i) => (
              <div key={i} className="h-3.5 rounded bg-zinc-200" style={{ width: `${70 + ((i * 13) % 28)}%` }} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
