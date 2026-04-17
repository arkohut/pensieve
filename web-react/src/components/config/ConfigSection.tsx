import type { ReactNode } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from '$/components/ui/button';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '$/components/ui/collapsible';

interface Props {
  title: string;
  description: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: ReactNode;
}

export function ConfigSection({ title, description, open, onOpenChange, children }: Props) {
  return (
    <div className="mb-6">
      <Collapsible open={open} onOpenChange={onOpenChange}>
        <div className="rounded-lg border bg-white">
          <CollapsibleTrigger className="w-full">
            <div className="flex items-center justify-between p-4">
              <div className="space-y-1 text-left">
                <h3 className="text-lg font-semibold">{title}</h3>
                <p className="text-sm text-muted-foreground">{description}</p>
              </div>
              <Button variant="ghost" size="icon" className="hover:bg-transparent">
                {open ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
              </Button>
            </div>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className="p-4 pt-0">
              <div className="grid gap-4">{children}</div>
            </div>
          </CollapsibleContent>
        </div>
      </Collapsible>
    </div>
  );
}
