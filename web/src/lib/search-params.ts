import { z } from 'zod';

const dateParam = z
  .string()
  .regex(/^\d{4}-\d{2}(-\d{2})?$/)
  .optional()
  .catch(undefined);

export const searchSchema = z.object({
  q: z.string().catch(''),
  submitted_q: z.string().catch(''),
  // start=0 is a sentinel for "no lower bound" (the user explicitly opted out
  // of the default 3-month window). nonnegative() lets the sentinel survive
  // schema validation.
  start: z.coerce.number().int().nonnegative().optional().catch(undefined),
  end: z.coerce.number().int().positive().optional().catch(undefined),
  library_ids: z.array(z.coerce.number().int()).catch([]),
  app_names: z.array(z.string()).catch([]),
  date: dateParam,
});

export type SearchParams = z.infer<typeof searchSchema>;

const DEFAULT_WINDOW_SEC = 90 * 24 * 60 * 60;

// Resolves the URL-level params into the params actually sent to the API.
// Without start/end/date in the URL we apply a 3-month default window so the
// search engine doesn't fan out across the full index. start=0 is the explicit
// "no lower bound" opt-out and unwinds to undefined here.
export function effectiveSearchParams(
  s: SearchParams,
  nowSec: number = Math.floor(Date.now() / 1000),
): SearchParams {
  if (s.start === 0) return { ...s, start: undefined };
  if (s.start !== undefined || s.end !== undefined || s.date) return s;
  return { ...s, start: nowSec - DEFAULT_WINDOW_SEC };
}

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
