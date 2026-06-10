import { cn } from '$/lib/utils';

// Mock "screenshot" of WeChat (微信). Hardcoded colors. Fills 1280×800.
const CHATS = [
  { n: '文件传输助手', m: '[文件] promo-deck.fig', t: '上午 9:24', active: true },
  { n: 'Pensieve 团队', m: '小川: 单卡那版定了', t: '上午 8:50', active: false },
  { n: '张三', m: '收到，晚点看', t: '昨天', active: false },
  { n: '前端交流群', m: '李四: 这个截图体系不错', t: '昨天', active: false },
];

export function WechatScreen() {
  return (
    <div className="flex h-full w-full bg-[#ededed] text-[17px] text-zinc-800">
      <div className="w-80 bg-[#e7e7e7]">
        <div className="px-4 py-3">
          <div className="flex h-9 items-center rounded bg-white/70 px-3 text-[15px] text-zinc-400">🔍 搜索</div>
        </div>
        {CHATS.map((c, i) => (
          <div key={i} className={cn('flex items-center gap-3 px-4 py-3', c.active && 'bg-[#c8c8c8]')}>
            <div className="h-12 w-12 shrink-0 rounded bg-gradient-to-br from-emerald-400 to-teal-500" />
            <div className="min-w-0 flex-1">
              <div className="flex justify-between">
                <span className="truncate font-medium">{c.n}</span>
                <span className="text-[13px] text-zinc-400">{c.t}</span>
              </div>
              <div className="truncate text-[14px] text-zinc-500">{c.m}</div>
            </div>
          </div>
        ))}
      </div>
      <div className="flex flex-1 flex-col bg-[#f5f5f5]">
        <div className="border-b border-zinc-200 px-6 py-4 text-[18px] font-medium">Pensieve 团队</div>
        <div className="flex-1 space-y-5 p-6">
          <div className="flex gap-3">
            <div className="h-11 w-11 shrink-0 rounded bg-gradient-to-br from-emerald-400 to-teal-500" />
            <div className="max-w-md rounded-lg bg-white px-4 py-2.5 shadow-sm">搜索页那版三张卡飘着，不像完整的东西</div>
          </div>
          <div className="flex justify-end gap-3">
            <div className="max-w-md rounded-lg bg-[#95ec69] px-4 py-2.5 shadow-sm">改成一整张搜索面板了，你看看</div>
            <div className="h-11 w-11 shrink-0 rounded bg-gradient-to-br from-orange-400 to-pink-500" />
          </div>
          <div className="flex gap-3">
            <div className="h-11 w-11 shrink-0 rounded bg-gradient-to-br from-emerald-400 to-teal-500" />
            <div className="max-w-md rounded-lg bg-white px-4 py-2.5 shadow-sm">这个就对了 👍</div>
          </div>
        </div>
        <div className="border-t border-zinc-200 bg-white px-6 py-4 text-zinc-400">发消息…</div>
      </div>
    </div>
  );
}
