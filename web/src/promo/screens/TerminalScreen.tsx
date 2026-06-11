// Mock "screenshot" of a terminal — hardcoded colors (it's a capture of another
// app, not Pensieve-themed). Authored to fill a 1280×800 ScreenBox.
export function TerminalScreen() {
  const prompt = (
    <>
      <span className="text-emerald-400">dev@mbp</span>{' '}
      <span className="text-sky-400">~/projects/memos</span>{' '}
      <span className="text-pink-400">❯</span>{' '}
    </>
  );
  return (
    <div className="flex h-full w-full flex-col bg-[#1b1b21] font-mono text-[21px] leading-relaxed text-zinc-200">
      <div className="flex items-center gap-2 bg-[#2a2a33] px-6 py-3.5">
        <span className="h-3.5 w-3.5 rounded-full bg-[#ff5f57]" />
        <span className="h-3.5 w-3.5 rounded-full bg-[#febc2e]" />
        <span className="h-3.5 w-3.5 rounded-full bg-[#28c840]" />
        <span className="ml-3 text-[15px] text-zinc-400">dev — zsh — 120×30</span>
      </div>
      <div className="flex-1 space-y-2.5 p-8">
        <div>{prompt}git status</div>
        <div className="text-zinc-400">
          On branch <span className="text-emerald-300">chip-promo-static-build</span>
        </div>
        <div className="text-zinc-400">Changes not staged for commit:</div>
        <div className="pl-8 text-red-400">modified:&nbsp;&nbsp; web/src/promo/scenes/SearchScene.tsx</div>
        <div className="pl-8 text-red-400">modified:&nbsp;&nbsp; web/src/promo/screens/IdeScreen.tsx</div>
        <div className="pt-1">
          {prompt}pnpm dev:promo
          <span className="ml-1 inline-block h-[0.95em] w-[0.5em] translate-y-[0.12em] bg-zinc-200" />
        </div>
      </div>
    </div>
  );
}
