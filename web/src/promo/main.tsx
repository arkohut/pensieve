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

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <Deck />
    </ThemeProvider>
  </StrictMode>,
);
