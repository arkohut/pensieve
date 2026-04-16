import { z } from 'zod';

export const searchSchema = z.object({
  q: z.string().catch(''),
  submitted_q: z.string().catch(''),
  start: z.coerce.number().int().positive().optional().catch(undefined),
  end: z.coerce.number().int().positive().optional().catch(undefined),
  library_ids: z.array(z.coerce.number().int()).catch([]),
  app_names: z.array(z.string()).catch([]),
});

export type SearchParams = z.infer<typeof searchSchema>;

export function buildSearchPath(params: SearchParams): string {
  const sp = new URLSearchParams();
  sp.append('q', params.q);
  if (params.start && params.start > 0) sp.append('start', String(params.start));
  if (params.end && params.end > 0) sp.append('end', String(params.end));
  if (params.library_ids.length) sp.append('library_ids', params.library_ids.join(','));
  if (params.app_names.length) sp.append('app_names', params.app_names.join(','));
  return `/search?${sp.toString()}`;
}
