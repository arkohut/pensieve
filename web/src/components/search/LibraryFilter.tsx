import { useTranslation } from 'react-i18next';
import { Button } from '$/components/ui/button';
import { Checkbox } from '$/components/ui/checkbox';
import { Label } from '$/components/ui/label';
import { Popover, PopoverContent, PopoverTrigger } from '$/components/ui/popover';
import { Separator } from '$/components/ui/separator';
import { useLibraries } from '$/lib/api/libraries';

interface Props {
  selectedLibraryIds: number[];
  onChange: (ids: number[]) => void;
}

export function LibraryFilter({ selectedLibraryIds, onChange }: Props) {
  const { t } = useTranslation();
  const { data: libraries = [] } = useLibraries();

  const allSelected = selectedLibraryIds.length === 0;
  const displayName = allSelected
    ? t('libraryFilter.all')
    : selectedLibraryIds
        .map((id) => libraries.find((l) => l.id === id)?.name ?? `#${id}`)
        .join(', ');

  function addLibraryId(id: number) {
    const next =
      libraries.length === selectedLibraryIds.length + 1
        ? []
        : [...selectedLibraryIds, id];
    onChange(next);
  }

  function removeLibraryId(id: number) {
    onChange(selectedLibraryIds.filter((x) => x !== id));
  }

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="border p-2 text-xs font-medium focus:outline-none"
        >
          <span className="max-w-[200px] truncate">{displayName}</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="mt-1 w-56 p-1" align="start" side="bottom">
        <div className="px-2 py-1.5 text-sm font-semibold">
          <Label className="text-sm font-semibold">{t('libraryFilter.repositoryFilter')}</Label>
        </div>
        <Separator className="my-1" />
        <div className="px-2 py-1.5">
          <div className="items-top mb-2 flex space-x-2">
            <Checkbox
              id="all-selected"
              checked={allSelected}
              disabled={allSelected}
              onCheckedChange={() => onChange([])}
            />
            <Label htmlFor="all-selected" className="flex items-center text-sm">
              {t('libraryFilter.selectAll')}
            </Label>
          </div>
          {libraries.map((library) => {
            const checked = selectedLibraryIds.includes(library.id);
            return (
              <div key={library.id} className="items-top mb-2 flex space-x-2">
                <Checkbox
                  id={`library-${library.id}`}
                  checked={checked}
                  onCheckedChange={(v) => {
                    if (v === true) addLibraryId(library.id);
                    else removeLibraryId(library.id);
                  }}
                />
                <Label htmlFor={`library-${library.id}`} className="flex items-center text-sm">
                  {library.name}#{library.id}
                </Label>
              </div>
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
}
