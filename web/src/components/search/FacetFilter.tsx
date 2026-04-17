import { Checkbox } from '$/components/ui/checkbox';
import { Label } from '$/components/ui/label';
import type { Facet } from '$/lib/api/types';

interface Props {
  facet: Facet;
  selected: string[];
  onToggle: (value: string, checked: boolean) => void;
}

export function FacetFilter({ facet, selected, onToggle }: Props) {
  const title = facet.field_name === 'app_names' ? 'App Names' : facet.field_name;
  return (
    <div className="mb-4">
      <h3 className="mb-2 text-lg font-semibold">{title}</h3>
      {facet.counts.map((item) => {
        const id = `${facet.field_name}-${item.value}`;
        const isChecked = selected.includes(item.value);
        return (
          <div key={item.value} className="items-top mb-2 flex space-x-2">
            <Checkbox
              id={id}
              checked={isChecked}
              onCheckedChange={(c) => onToggle(item.value, c === true)}
            />
            <Label htmlFor={id} className="flex items-center text-sm">
              {item.value} ({item.count})
            </Label>
          </div>
        );
      })}
    </div>
  );
}
