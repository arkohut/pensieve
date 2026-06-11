// Mock "screenshot" of X / Twitter (dark). Hardcoded colors. Fills 1280×800.
export function TwitterScreen() {
  return (
    <div className="flex h-full w-full bg-black text-[18px] text-zinc-100">
      {/* left rail */}
      <div className="flex w-72 flex-col items-start gap-6 px-9 py-7 text-[21px]">
        <span className="text-[34px] font-bold leading-none">𝕏</span>
        <div className="space-y-5 text-zinc-300">
          <div>Home</div>
          <div>Explore</div>
          <div>Notifications</div>
          <div>Messages</div>
        </div>
        <span className="mt-2 w-44 rounded-full bg-white py-3 text-center font-bold text-black">Post</span>
      </div>
      {/* tweet column */}
      <div className="flex-1 border-x border-zinc-800">
        <div className="border-b border-zinc-800 px-6 py-4 text-[20px] font-bold">Home</div>
        <div className="flex gap-4 px-6 py-5">
          <div className="h-14 w-14 shrink-0 rounded-full bg-gradient-to-br from-sky-400 to-indigo-500" />
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="font-bold">Pensieve</span>
              <span className="text-zinc-500">@pensieve_app · 2h</span>
            </div>
            <div className="mt-1.5 leading-relaxed">
              Your screen, searchable. Pensieve quietly records what you see and lets you find any
              moment later — fully local, on your machine. 🧠
            </div>
            <div className="mt-3 aspect-video w-full rounded-2xl border border-zinc-800 bg-gradient-to-br from-zinc-800 to-zinc-900" />
            <div className="mt-3 flex justify-between pr-20 text-[16px] text-zinc-500">
              <span>💬 48</span>
              <span>🔁 312</span>
              <span>♥ 2.1K</span>
              <span>📊 84K</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
