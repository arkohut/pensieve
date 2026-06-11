import { cn } from '$/lib/utils';

// Mock "screenshot" of Gmail. Hardcoded colors. Fills 1280×800.
const ROWS = [
  { sender: 'Pensieve', subject: 'Your weekly recap is ready', snippet: '— 1,488,618 screens indexed this week', time: '9:24 AM', unread: true },
  { sender: 'GitHub', subject: '[acme/pensieve] PR #128 merged', snippet: '— keep watch alive when the OS reports…', time: '8:02 AM', unread: true },
  { sender: 'Vercel', subject: 'Deployment ready', snippet: '— promo-deck is live in preview', time: 'Yesterday', unread: false },
  { sender: 'Figma', subject: 'A. commented on “Promo deck”', snippet: '— love the single-card treatment', time: 'Yesterday', unread: false },
  { sender: 'Stripe', subject: 'Your receipt', snippet: '— payment of $20.00 to OpenAI', time: 'Mon', unread: false },
];

export function GmailScreen() {
  return (
    <div className="flex h-full w-full flex-col bg-[#f6f8fc] text-[17px] text-zinc-800">
      <div className="flex items-center gap-5 px-6 py-4">
        <span className="text-[22px] font-medium text-zinc-600">
          <span className="text-[#ea4335] font-bold">M</span> Gmail
        </span>
        <div className="flex h-11 max-w-2xl flex-1 items-center rounded-full bg-[#eaf1fb] px-5 text-zinc-500">
          Search mail
        </div>
        <div className="h-9 w-9 rounded-full bg-gradient-to-br from-orange-400 to-pink-500" />
      </div>
      <div className="flex flex-1 overflow-hidden">
        <div className="w-60 px-4 py-3">
          <div className="inline-flex items-center gap-2 rounded-2xl bg-white px-5 py-3 shadow-sm">
            <span className="text-[24px] leading-none text-[#c5221f]">＋</span>
            <span className="text-zinc-700">Compose</span>
          </div>
          <div className="mt-4 space-y-1 text-[16px]">
            <div className="rounded-r-full bg-[#fce8e6] px-5 py-2 font-semibold text-[#c5221f]">Inbox</div>
            <div className="px-5 py-2 text-zinc-600">Starred</div>
            <div className="px-5 py-2 text-zinc-600">Sent</div>
            <div className="px-5 py-2 text-zinc-600">Drafts</div>
          </div>
        </div>
        <div className="flex-1 overflow-hidden rounded-tl-2xl bg-white">
          {ROWS.map((r, i) => (
            <div key={i} className="flex items-center gap-4 border-b border-zinc-100 px-6 py-3.5">
              <span className="text-zinc-300">☆</span>
              <span className={cn('w-44 shrink-0 truncate', r.unread ? 'font-bold text-zinc-900' : 'text-zinc-600')}>
                {r.sender}
              </span>
              <span className="flex-1 truncate">
                <span className={r.unread ? 'font-bold text-zinc-900' : 'text-zinc-700'}>{r.subject}</span>
                <span className="text-zinc-500"> {r.snippet}</span>
              </span>
              <span className="shrink-0 text-[14px] text-zinc-500">{r.time}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
