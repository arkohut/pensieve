import { z } from 'zod';

const dateParam = z
  .string()
  .regex(/^\d{4}-\d{2}(-\d{2})?$/)
  .optional()
  .catch(undefined);

export const searchSchema = z.object({
  q: z.string().catch(''),
  submitted_q: z.string().catch(''),
  start: z.coerce.number().int().positive().optional().catch(undefined),
  end: z.coerce.number().int().positive().optional().catch(undefined),
  library_ids: z.array(z.coerce.number().int()).catch([]),
  app_names: z.array(z.string()).catch([]),
  date: dateParam,
});

export type SearchParams = z.infer<typeof searchSchema>;

/** Date scope for the facet query — always at most month-level ('YYYY-MM').
 * 'YYYY-MM-DD' → 'YYYY-MM' (so day selection still shows sibling days),
 * 'YYYY-MM'    → 'YYYY-MM' (so month selection drills into days within),
 * undefined    → undefined (top level — months across the whole result).
 */
export function facetScope(date: string | undefined): string | undefined {
  return date?.slice(0, 7);
}

export function buildSearchPath(params: SearchParams): string {
  const sp = new URLSearchParams();
  sp.append('q', params.q);
  if (params.start && params.start > 0) sp.append('start', String(params.start));
  if (params.end && params.end > 0) sp.append('end', String(params.end));
  if (params.library_ids.length) sp.append('library_ids', params.library_ids.join(','));
  if (params.app_names.length) sp.append('app_names', params.app_names.join(','));
  if (params.date) sp.append('date', params.date);
  return `/search?${sp.toString()}`;
}
