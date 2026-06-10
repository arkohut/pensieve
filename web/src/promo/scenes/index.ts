import type { ComponentType } from 'react';
import { ProcessingPillScene } from './ProcessingPillScene';
import { SearchScene } from './SearchScene';

export interface Scene {
  id: string;
  title: string;
  Component: ComponentType;
}

export const SCENES: Scene[] = [
  { id: 'processing-pill', title: 'Processing status', Component: ProcessingPillScene },
  { id: 'search', title: 'Search', Component: SearchScene },
];
