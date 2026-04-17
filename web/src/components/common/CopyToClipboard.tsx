import { useState } from 'react';
import { Copy, Check } from 'lucide-react';
import { Button } from '$/components/ui/button';
import { toast } from 'sonner';
import { cn } from '$/lib/utils';

interface Props {
  text: string;
  className?: string;
}

export function CopyToClipboard({ text, className }: Props) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error('Failed to copy');
    }
  }

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={handleCopy}
      className={cn('h-6 w-6', className)}
    >
      {copied ? <Check size={14} /> : <Copy size={14} />}
    </Button>
  );
}
