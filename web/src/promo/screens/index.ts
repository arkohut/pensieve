import type { ComponentType } from 'react';
import { DocsScreen } from './DocsScreen';
import { GmailScreen } from './GmailScreen';
import { IdeScreen } from './IdeScreen';
import { NewsScreen } from './NewsScreen';
import { PptScreen } from './PptScreen';
import { TerminalScreen } from './TerminalScreen';
import { TwitterScreen } from './TwitterScreen';
import { WechatScreen } from './WechatScreen';
import { YouTubeScreen } from './YouTubeScreen';

export interface MockScreen {
  id: string;
  label: string;
  Component: ComponentType;
}

/** Reusable mock "screenshots" of other apps — for search thumbnails, single-shot
 *  and context views. Authored at 1280×800; render via ScreenBox to size them. */
export const SCREENS: MockScreen[] = [
  { id: 'youtube', label: 'YouTube', Component: YouTubeScreen },
  { id: 'twitter', label: 'X / Twitter', Component: TwitterScreen },
  { id: 'news', label: 'News article', Component: NewsScreen },
  { id: 'gmail', label: 'Gmail', Component: GmailScreen },
  { id: 'wechat', label: '微信 WeChat', Component: WechatScreen },
  { id: 'docs', label: 'Google Docs', Component: DocsScreen },
  { id: 'ppt', label: 'PowerPoint', Component: PptScreen },
  { id: 'terminal', label: 'Terminal', Component: TerminalScreen },
  { id: 'ide', label: 'IDE', Component: IdeScreen },
];
