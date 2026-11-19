import type { LatLng, RouteOption } from '../types';

const R_MI = 3958.7613;
const rad = (d: number) => (d * Math.PI) / 180;

export function haversineMi(a: LatLng, b: LatLng): number {
  const dLat = rad(b[0] - a[0]);
  const dLon = rad(b[1] - a[1]);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a[0])) * Math.cos(rad(b[0])) * Math.sin(dLon / 2) ** 2;
  return 2 * R_MI * Math.asin(Math.min(1, Math.sqrt(h)));
}

export function cumulativeMiles(coords: LatLng[]): number[] {
  const out = [0];
  for (let i = 1; i < coords.length; i++) out.push(out[i - 1] + haversineMi(coords[i - 1], coords[i]));
  return out;
}

/** Point at a given fraction (0–1) of a polyline's length. */
export function pointAtFraction(coords: LatLng[], cum: number[], fraction: number): LatLng {
  const target = Math.max(0, Math.min(1, fraction)) * cum[cum.length - 1];
  let i = 1;
  while (i < cum.length - 1 && cum[i] < target) i++;
  const seg = cum[i] - cum[i - 1];
  const t = seg > 0 ? (target - cum[i - 1]) / seg : 0;
  const [a, b] = [coords[i - 1], coords[i]];
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
}

/**
 * Where the truck is at a given time, interpolating mile-vs-ETA between checkpoints
 * (so HOS rest stops show the truck parked) and then mapping mile to the road geometry.
 */
export function truckPosition(route: RouteOption, cum: number[], when: Date): LatLng {
  const cps = route.checkpoints;
  const t = when.getTime();
  const total = cum[cum.length - 1];
  let mile = route.distance_mi;
  if (t <= Date.parse(cps[0].eta)) mile = 0;
  else {
    for (let i = 1; i < cps.length; i++) {
      const t0 = Date.parse(cps[i - 1].eta);
      const t1 = Date.parse(cps[i].eta);
      if (t <= t1) {
        const f = t1 > t0 ? (t - t0) / (t1 - t0) : 1;
        mile = cps[i - 1].mile + (cps[i].mile - cps[i - 1].mile) * f;
        break;
      }
    }
  }
  return pointAtFraction(route.geometry, cum, total > 0 ? mile / route.distance_mi : 0);
}

/** Uniformly thin a polyline to at most `max` points (keeps both ends). */
export function downsample(coords: LatLng[], max: number): LatLng[] {
  if (coords.length <= max) return coords;
  const step = (coords.length - 1) / (max - 1);
  return Array.from({ length: max }, (_, i) => coords[Math.round(i * step)]);
}
