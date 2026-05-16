import { describe, expect, it } from 'vitest';
import { groupHits } from '$/lib/group-hits';
import type { Hit } from '$/lib/api/types';

function hit(id: number, ts: string, app = 'iTerm2', win = 'Claude Code'): Hit {
  return {
    document: {
      id,
      library_id: 1,
      folder_id: 1,
      filepath: `/x/${id}.webp`,
      filename: `${id}.webp`,
      file_created_at: ts,
      file_last_modified_at: ts,
      tags: [],
      metadata_entries: [
        { key: 'active_app', source: 'system_generated', value: app },
        { key: 'active_window', source: 'system_generated', value: win },
      ],
    },
  };
}

describe('groupHits', () => {
  it('returns empty for empty input', () => {
    expect(groupHits([])).toEqual([]);
  });

  it('keeps unrelated hits separate', () => {
    const hits = [
      hit(1, '2026-05-10T00:11:13Z', 'iTerm2', 'Claude Code'),
      hit(2, '2026-05-10T00:11:00Z', 'Chrome', 'GitHub'),
      hit(3, '2026-05-10T00:10:50Z', 'iTerm2', 'Vim'),
    ];
    const groups = groupHits(hits);
    expect(groups.map((g) => [g.rep.document.id, g.count])).toEqual([
      [1, 1],
      [2, 1],
      [3, 1],
    ]);
  });

  it('folds consecutive hits in the same window within 60s', () => {
    const hits = [
      hit(1, '2026-05-10T00:11:13Z'),
      hit(2, '2026-05-10T00:11:07Z'),
      hit(3, '2026-05-10T00:11:00Z'),
      hit(4, '2026-05-10T00:10:55Z'),
    ];
    const groups = groupHits(hits);
    expect(groups).toHaveLength(1);
    expect(groups[0].rep.document.id).toBe(1);
    expect(groups[0].count).toBe(4);
    expect(groups[0].flatIndex).toBe(0);
  });

  it('breaks the group when the time gap exceeds 60s', () => {
    const hits = [
      hit(1, '2026-05-10T00:11:13Z'),
      hit(2, '2026-05-10T00:11:00Z'), // 13s gap → grouped
      hit(3, '2026-05-10T00:09:50Z'), // 70s gap from id=2 → new group
    ];
    const groups = groupHits(hits);
    expect(groups.map((g) => [g.rep.document.id, g.count])).toEqual([
      [1, 2],
      [3, 1],
    ]);
  });

  it('breaks the group when the active window changes', () => {
    const hits = [
      hit(1, '2026-05-10T00:11:13Z', 'iTerm2', 'Claude Code'),
      hit(2, '2026-05-10T00:11:10Z', 'iTerm2', 'Vim'),
    ];
    const groups = groupHits(hits);
    expect(groups).toHaveLength(2);
  });

  it('flatIndex points back into the original array', () => {
    const hits = [
      hit(1, '2026-05-10T00:11:13Z', 'iTerm2', 'A'),
      hit(2, '2026-05-10T00:11:10Z', 'iTerm2', 'A'),
      hit(3, '2026-05-10T00:10:00Z', 'Chrome', 'B'),
      hit(4, '2026-05-10T00:09:55Z', 'Chrome', 'B'),
    ];
    const groups = groupHits(hits);
    expect(groups.map((g) => g.flatIndex)).toEqual([0, 2]);
  });

  it('keeps hits without app/window metadata separate (static libraries do not fold)', () => {
    const bare = (id: number, ts: string): Hit => ({
      document: {
        id,
        library_id: 1,
        folder_id: 1,
        filepath: `/x/${id}.webp`,
        filename: `${id}.webp`,
        file_created_at: ts,
        file_last_modified_at: ts,
        tags: [],
        metadata_entries: [],
      },
    });
    const groups = groupHits([bare(1, '2026-05-10T00:11:13Z'), bare(2, '2026-05-10T00:11:10Z')]);
    expect(groups.map((g) => [g.rep.document.id, g.count])).toEqual([
      [1, 1],
      [2, 1],
    ]);
  });
});
