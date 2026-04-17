interface OCRRow {
  dt_boxes: unknown;
  rec_txt: string;
  score: number;
}

interface Props {
  ocrData: OCRRow[];
}

export function OCRTable({ ocrData }: Props) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full max-w-3xl table-fixed bg-card">
        <thead>
          <tr>
            <th className="w-4/5 py-2">Text</th>
            <th className="w-1/5 py-2">Score</th>
          </tr>
        </thead>
        <tbody>
          {ocrData.map((row, i) => (
            <tr key={i} className="hover:bg-accent">
              <td className="truncate border px-4 py-2">{row.rec_txt}</td>
              <td className="border px-4 py-2 text-center">{row.score.toFixed(3)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function isValidOCRDataStructure(data: unknown): data is OCRRow[] {
  if (!Array.isArray(data)) return false;
  for (const item of data) {
    if (
      typeof item !== 'object' ||
      item === null ||
      !('dt_boxes' in item) ||
      !('rec_txt' in item) ||
      !('score' in item)
    ) {
      return false;
    }
    if (
      !Array.isArray((item as OCRRow).dt_boxes) ||
      typeof (item as OCRRow).rec_txt !== 'string' ||
      typeof (item as OCRRow).score !== 'number'
    ) {
      return false;
    }
  }
  return true;
}
