/**
 * Turns the coarse corridor grid returned by /api/heatmap into smooth raster frames.
 *
 * - Values are bilinearly interpolated *before* colour mapping (no colour banding).
 * - Grid nodes outside the corridor are missing; their weight is dropped and the
 *   remaining coverage fades alpha, giving soft corridor edges.
 * - Rows are placed in Web-Mercator space so the image lines up with the basemap.
 * - Each (field, hour) frame is rendered once and cached as a data URL, so dragging
 *   the time slider or playing the animation only swaps an image source.
 */
import type { HeatField, HeatmapResponse } from '../types';

type RGBA = [number, number, number, number];
type Stop = [number, RGBA];

interface Scale {
  max: number;
  unit: string;
  stops: Stop[];
}

export const HEAT_SCALES: Record<HeatField, Scale> = {
  risk: {
    max: 4,
    unit: 'level',
    stops: [
      [0, [34, 197, 94, 30]],
      [1, [234, 179, 8, 140]],
      [2, [249, 115, 22, 170]],
      [3, [220, 38, 38, 195]],
      [4, [126, 34, 206, 215]],
    ],
  },
  wind: {
    max: 60,
    unit: 'mph',
    stops: [
      [0, [56, 189, 248, 0]],
      [10, [56, 189, 248, 50]],
      [25, [234, 179, 8, 140]],
      [35, [249, 115, 22, 175]],
      [45, [220, 38, 38, 200]],
      [55, [126, 34, 206, 220]],
    ],
  },
  rain: {
    max: 1.2,
    unit: 'in/hr',
    stops: [
      [0, [59, 130, 246, 0]],
      [0.01, [96, 165, 250, 70]],
      [0.1, [37, 99, 235, 140]],
      [0.25, [234, 179, 8, 170]],
      [0.5, [220, 38, 38, 200]],
      [1.0, [126, 34, 206, 220]],
    ],
  },
  snow: {
    max: 3.5,
    unit: 'in/hr',
    stops: [
      [0, [186, 230, 253, 0]],
      [0.05, [186, 230, 253, 90]],
      [0.5, [56, 189, 248, 150]],
      [1.0, [249, 115, 22, 175]],
      [2.0, [220, 38, 38, 200]],
      [3.0, [126, 34, 206, 220]],
    ],
  },
};

const LUT_SIZE = 256;

function buildLut(scale: Scale): Uint8ClampedArray {
  const lut = new Uint8ClampedArray(LUT_SIZE * 4);
  const { stops, max } = scale;
  for (let i = 0; i < LUT_SIZE; i++) {
    const v = (i / (LUT_SIZE - 1)) * max;
    let j = 1;
    while (j < stops.length - 1 && stops[j][0] < v) j++;
    const [v0, c0] = stops[j - 1];
    const [v1, c1] = stops[j];
    const t = Math.max(0, Math.min(1, (v - v0) / (v1 - v0)));
    for (let k = 0; k < 4; k++) lut[i * 4 + k] = c0[k] + (c1[k] - c0[k]) * t;
  }
  return lut;
}

/** CSS gradient matching a scale, for the legend. */
export function legendGradient(field: HeatField): string {
  const { stops, max } = HEAT_SCALES[field];
  const parts = stops.map(([v, [r, g, b, a]]) => `rgba(${r},${g},${b},${Math.max(a, 60) / 255}) ${(v / max) * 100}%`);
  return `linear-gradient(to right, ${parts.join(', ')})`;
}

const mercY = (lat: number) => Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360));
const invMercY = (y: number) => (360 / Math.PI) * Math.atan(Math.exp(y)) - 90;

const MAX_PIXELS = 520;

export class HeatmapRaster {
  readonly bounds: [[number, number], [number, number]];
  private readonly width: number;
  private readonly height: number;
  private readonly rowPos: Float32Array; // fractional grid row for each pixel row
  private readonly colPos: Float32Array; // fractional grid col for each pixel column
  private readonly canvas: HTMLCanvasElement;
  private readonly cache = new Map<string, string>();
  private readonly luts = new Map<HeatField, Uint8ClampedArray>();
  private readonly data: HeatmapResponse;

  constructor(data: HeatmapResponse) {
    this.data = data;
    const { lat0, lon0, dlat, dlon, rows, cols } = data.grid;
    const latMax = lat0 + (rows - 1) * dlat;
    const lonMax = lon0 + (cols - 1) * dlon;
    this.bounds = [
      [lat0, lon0],
      [latMax, lonMax],
    ];

    const scale = Math.max(1, Math.floor(MAX_PIXELS / Math.max(rows, cols)));
    this.width = (cols - 1) * scale;
    this.height = (rows - 1) * scale;

    const yTop = mercY(latMax);
    const yBottom = mercY(lat0);
    this.rowPos = new Float32Array(this.height);
    for (let py = 0; py < this.height; py++) {
      const lat = invMercY(yTop + ((py + 0.5) / this.height) * (yBottom - yTop));
      this.rowPos[py] = (lat - lat0) / dlat;
    }
    this.colPos = new Float32Array(this.width);
    for (let px = 0; px < this.width; px++) this.colPos[px] = ((px + 0.5) / this.width) * (cols - 1);

    this.canvas = document.createElement('canvas');
    this.canvas.width = this.width;
    this.canvas.height = this.height;
  }

  get hours(): number {
    return this.data.hours;
  }

  frame(field: HeatField, hour: number): string {
    const key = `${field}:${hour}`;
    let url = this.cache.get(key);
    if (!url) {
      url = this.render(field, hour);
      this.cache.set(key, url);
    }
    return url;
  }

  /** Render remaining frames for a field in small idle-time batches. */
  prerender(field: HeatField, isCancelled: () => boolean): void {
    let hour = 0;
    const step = () => {
      if (isCancelled()) return;
      const end = Math.min(this.data.hours, hour + 4);
      for (; hour <= end; hour++) this.frame(field, hour);
      if (hour <= this.data.hours) setTimeout(step, 16);
    };
    setTimeout(step, 50);
  }

  private grid(field: HeatField, hour: number): Float32Array {
    const { rows, cols } = this.data.grid;
    const values = new Float32Array(rows * cols).fill(NaN);
    const series = this.data.fields[field];
    this.data.nodes.forEach(([r, c], i) => {
      const v = series[i]?.[hour];
      if (v != null) values[r * cols + c] = v;
    });
    return values;
  }

  private lut(field: HeatField): Uint8ClampedArray {
    let lut = this.luts.get(field);
    if (!lut) {
      lut = buildLut(HEAT_SCALES[field]);
      this.luts.set(field, lut);
    }
    return lut;
  }

  private render(field: HeatField, hour: number): string {
    const { rows, cols } = this.data.grid;
    const values = this.grid(field, hour);
    const lut = this.lut(field);
    const max = HEAT_SCALES[field].max;
    const ctx = this.canvas.getContext('2d')!;
    const image = ctx.createImageData(this.width, this.height);
    const px = image.data;

    for (let y = 0; y < this.height; y++) {
      const gr = this.rowPos[y];
      const r0 = Math.min(rows - 2, Math.max(0, Math.floor(gr)));
      const fy = Math.min(1, Math.max(0, gr - r0));
      for (let x = 0; x < this.width; x++) {
        const gc = this.colPos[x];
        const c0 = Math.min(cols - 2, Math.floor(gc));
        const fx = gc - c0;
        const i00 = r0 * cols + c0;
        let sum = 0;
        let weight = 0;
        const v00 = values[i00];
        const v01 = values[i00 + 1];
        const v10 = values[i00 + cols];
        const v11 = values[i00 + cols + 1];
        if (v00 === v00) { const w = (1 - fx) * (1 - fy); sum += v00 * w; weight += w; } // x === x is a fast !isNaN
        if (v01 === v01) { const w = fx * (1 - fy); sum += v01 * w; weight += w; }
        if (v10 === v10) { const w = (1 - fx) * fy; sum += v10 * w; weight += w; }
        if (v11 === v11) { const w = fx * fy; sum += v11 * w; weight += w; }
        if (weight < 0.05) continue;
        const v = sum / weight;
        const li = Math.round((Math.min(max, Math.max(0, v)) / max) * (LUT_SIZE - 1)) * 4;
        const o = (y * this.width + x) * 4; // pixel rows run north → south (see rowPos)
        px[o] = lut[li];
        px[o + 1] = lut[li + 1];
        px[o + 2] = lut[li + 2];
        px[o + 3] = lut[li + 3] * Math.min(1, weight * 1.6);
      }
    }
    ctx.putImageData(image, 0, 0);
    return this.canvas.toDataURL('image/png');
  }
}
