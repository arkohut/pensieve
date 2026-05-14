interface Tile {
  x: number;
  y: number;
}

const TILE = 0.86;
const RADIUS = 0.16;
const OFFSET_Y = 0.56;

// P spans logical x∈[1,6], y∈[0,6]; NW→SE diagonal extent = (6-1) + (6-0).
const DIAGONAL_EXTENT = 11;

const GRADIENT_STOPS = ['#1E2530', '#C46153', '#E27B6A', '#EEE9E5'];

const TILES: Tile[] = [
  { x: 1, y: 0 }, { x: 2, y: 0 }, { x: 3, y: 0 }, { x: 4, y: 0 }, { x: 5, y: 0 },
  { x: 1, y: 1 }, { x: 2, y: 1 }, { x: 3, y: 1 }, { x: 4, y: 1 }, { x: 5, y: 1 }, { x: 6, y: 1 },
  { x: 1, y: 2 }, { x: 2, y: 2 }, { x: 5, y: 2 }, { x: 6, y: 2 },
  { x: 1, y: 3 }, { x: 2, y: 3 }, { x: 5, y: 3 }, { x: 6, y: 3 },
  { x: 1, y: 4 }, { x: 2, y: 4 }, { x: 3, y: 4 }, { x: 4, y: 4 }, { x: 5, y: 4 },
  { x: 1, y: 5 }, { x: 2, y: 5 }, { x: 3, y: 5 }, { x: 4, y: 5 },
  { x: 1, y: 6 }, { x: 2, y: 6 },
];

function hexToRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function rgbToHex(rgb: number[]): string {
  return (
    '#' +
    rgb
      .map((v) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, '0'))
      .join('')
  );
}

function lerp(a: string, b: string, t: number): string {
  const ca = hexToRgb(a);
  const cb = hexToRgb(b);
  return rgbToHex(ca.map((v, i) => v + (cb[i] - v) * t));
}

function multiLerp(stops: readonly string[], t: number): string {
  if (t <= 0) return stops[0];
  if (t >= 1) return stops[stops.length - 1];
  const idx = t * (stops.length - 1);
  const i = Math.floor(idx);
  return lerp(stops[i], stops[i + 1], idx - i);
}

function tile({ x, y }: Tile, compact: boolean) {
  const size = compact ? 0.92 : TILE;
  const radius = compact ? 0.12 : RADIUS;
  const offset = compact ? 0.04 : 0;
  const fill = multiLerp(GRADIENT_STOPS, (x - 1 + y) / DIAGONAL_EXTENT);
  return `  <rect x="${x + offset}" y="${y + OFFSET_Y + offset}" width="${size}" height="${size}" rx="${radius}" ry="${radius}" fill="${fill}" />\n`;
}

export function generateLogo(size: number, withBorder: boolean, hasGap: boolean): string {
  const compact = !hasGap || size <= 32;
  const viewBox = withBorder ? `0 0 8 8` : `0.75 0.3 6.5 7.5`;

  let svg = `<svg width="${size}" height="${size}" viewBox="${viewBox}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Pensieve logo">\n`;
  for (const t of TILES) {
    svg += tile(t, compact);
  }
  svg += `</svg>`;

  return svg;
}
