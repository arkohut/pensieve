import type { ComponentType } from 'react';
import { ProcessingPillScene } from './ProcessingPillScene';

export interface Scene {
  id: string;
  title: string;
  Component: ComponentType;
}

export const SCENES: Scene[] = [
  { id: 'processing-pill', title: 'Processing status', Component: ProcessingPillScene },
];
