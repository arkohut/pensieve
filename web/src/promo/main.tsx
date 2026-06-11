import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import '@fontsource-variable/geist';
import '@fontsource-variable/jetbrains-mono';
import '@fontsource/caveat';
import '@fontsource/ma-shan-zheng';

import { ThemeProvider } from '$/components/common/ThemeProvider';
import { Deck } from './Deck';
import '../styles/globals.css';
import '$/lib/i18n';

// Promo images must be deterministic: theme is driven by ?theme=light|dark
// (default light) and forced via next-themes, so it ignores localStorage / OS.
const forcedTheme =
  new URLSearchParams(window.location.search).get('theme') === 'dark' ? 'dark' : 'light';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider forcedTheme={forcedTheme}>
      <Deck />
    </ThemeProvider>
  </StrictMode>,
);
