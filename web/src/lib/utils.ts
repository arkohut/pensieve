import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function translateAppName(appName: string): string | undefined {
  const cleanedAppName = appName.replace(/\.exe$/, '');

  const appIconMap: Record<string, string> = {
    chrome: 'Chrome',
    firefox: 'Globe',
    edge: 'Globe',
    msedge: 'Globe',
    code: 'Code',
    cursor: 'Code',

    'windows app beta': 'LayoutGrid',
    'windows app preview': 'LayoutGrid',

    'google chrome': 'Chrome',
    iina: 'Youtube',
    微信: 'MessageSquareCode',
    预览: 'Eye',
    iterm2: 'SquareTerminal',
    企业微信: 'MessageSquareCode',
    'intellij idea': 'Code',
    'microsoft edge': 'Globe',
    腾讯会议: 'Phone',
    访达: 'Folder',
    邮件: 'Mail',
    备忘录: 'NotebookTabs',
    日历: 'CalendarFold',
    usernotificationcenter: 'Bell',
    electron: 'Atom',
    safari浏览器: 'Compass',
    熊掌记: 'NotebookTabs',
    alacritty: 'SquareTerminal',
    系统设置: 'Settings',
    股市: 'CircleDollarSign',
    活动监视器: 'Activity',
    'brave browser': 'Globe',

    windowsterminal: 'SquareTerminal',
    explorer: 'Folder',
    'clash for windows': 'Globe',
    mpv: 'Youtube',
    searchhost: 'Search',
    lockapp: 'Lock',
    thunder: 'CloudDownload',
    xlliveud: 'CloudDownload',
    'ollama app': 'Bot',
    githubdesktop: 'Github',
  };

  return appIconMap[cleanedAppName.toLowerCase()];
}

export function filename(path: string): string {
  const splits = path.split('/');
  return splits[splits.length - 1] ?? path;
}

export function formatDate(dateStr: string): string {
  if (!dateStr) return '';
  try {
    const utcDate = dateStr.endsWith('Z') ? dateStr : dateStr + 'Z';
    const date = new Date(utcDate);
    return date.toLocaleString(undefined, {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });
  } catch {
    try {
      const date = new Date(dateStr);
      return date.toLocaleString(undefined, {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      });
    } catch {
      return dateStr;
    }
  }
}
