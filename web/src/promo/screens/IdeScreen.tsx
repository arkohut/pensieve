import type { ReactNode } from 'react';

// Mock "screenshot" of a VS Code-like editor. Hardcoded colors. Fills 1280×800.
function Ln({ n, children }: { n: number; children: ReactNode }) {
  return (
    <div className="flex gap-6">
      <span className="w-6 shrink-0 text-right text-zinc-600">{n}</span>
      <span>{children}</span>
    </div>
  );
}

export function IdeScreen() {
  return (
    <div className="flex h-full w-full bg-[#1e1e1e] text-zinc-300">
      {/* activity bar */}
      <div className="flex w-16 flex-col items-center gap-7 bg-[#333333] py-6">
        <div className="h-7 w-7 rounded bg-zinc-300" />
        <div className="h-7 w-7 rounded bg-zinc-600" />
        <div className="h-7 w-7 rounded bg-zinc-600" />
        <div className="h-7 w-7 rounded bg-zinc-600" />
      </div>
      {/* explorer */}
      <div className="w-64 bg-[#252526] py-5 text-[17px] text-zinc-400">
        <div className="px-5 text-[13px] uppercase tracking-wider text-zinc-500">Explorer</div>
        <div className="mt-4 space-y-2.5 px-5">
          <div>▾ memos / promo</div>
          <div className="pl-5 text-sky-300">IdeScreen.tsx</div>
          <div className="pl-5">SearchScene.tsx</div>
          <div className="pl-5">YouTubeScreen.tsx</div>
          <div className="pl-5">vite.config.ts</div>
        </div>
      </div>
      {/* editor */}
      <div className="flex flex-1 flex-col">
        <div className="flex bg-[#2d2d2d] text-[16px]">
          <div className="bg-[#1e1e1e] px-6 py-3 text-sky-300">IdeScreen.tsx</div>
          <div className="px-6 py-3 text-zinc-500">SearchScene.tsx</div>
        </div>
        <div className="flex-1 space-y-2.5 p-8 font-mono text-[21px] leading-relaxed">
          <Ln n={1}>
            <span className="text-[#c586c0]">export function</span>{' '}
            <span className="text-[#dcdcaa]">IdeScreen</span>() {'{'}
          </Ln>
          <Ln n={2}>
            <span className="pl-6 text-[#c586c0]">return</span> <span>(</span>
          </Ln>
          <Ln n={3}>
            <span className="pl-12 text-zinc-500">&lt;</span>
            <span className="text-[#4ec9b0]">div</span>{' '}
            <span className="text-[#9cdcfe]">className</span>=
            <span className="text-[#ce9178]">"editor"</span>
            <span className="text-zinc-500">&gt;</span>
          </Ln>
          <Ln n={4}>
            <span className="pl-[4.5rem] text-[#ce9178]">"hello, Pensieve"</span>
          </Ln>
          <Ln n={5}>
            <span className="pl-12 text-zinc-500">&lt;/</span>
            <span className="text-[#4ec9b0]">div</span>
            <span className="text-zinc-500">&gt;</span>
          </Ln>
          <Ln n={6}>
            <span className="pl-6">)</span>
          </Ln>
          <Ln n={7}>{'}'}</Ln>
        </div>
        <div className="bg-[#007acc] px-6 py-2.5 text-[15px] text-white">
          ⎇ chip-promo-static-build&nbsp;&nbsp;&nbsp; ⓧ 0&nbsp; ⚠ 0&nbsp;&nbsp;&nbsp; TypeScript React
        </div>
      </div>
    </div>
  );
}
