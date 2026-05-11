import { useTranslation } from 'react-i18next';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '$/components/ui/dropdown-menu';
import { Button } from '$/components/ui/button';
import { Globe } from 'lucide-react';

const LANGS = [
  { code: 'en', label: 'English' },
  { code: 'zh', label: '中文' },
] as const;

export function LanguageSwitcher() {
  const { i18n, t } = useTranslation();
  const current = i18n.language.startsWith('zh') ? 'zh' : 'en';
  const currentLabel = LANGS.find((l) => l.code === current)?.label ?? t('language');

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 text-muted-foreground hover:text-foreground"
          aria-label={`Language: ${currentLabel}`}
          title={`Language: ${currentLabel}`}
        >
          <Globe size={16} />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {LANGS.map((l) => (
          <DropdownMenuItem key={l.code} onClick={() => void i18n.changeLanguage(l.code)}>
            {l.label}
            {l.code === current && <span className="ml-auto text-xs">✓</span>}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
