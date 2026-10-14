import type { FeatureCollection } from "geojson";
import type { Unit } from "@/sim/types";

/** Maximum historical coordinates stored per unit trail to avoid unbounded memory */
export const MAX_TRAIL_LENGTH = 25;

/** Calculate bearing in degrees from point A to point B */
export function calculateBearing(a: [number, number], b: [number, number]): number {
  const y = Math.sin(((b[1] - a[1]) * Math.PI) / 180) * Math.cos((b[0] * Math.PI) / 180);
  const x =
    Math.cos((a[0] * Math.PI) / 180) * Math.sin((b[0] * Math.PI) / 180) -
    Math.sin((a[0] * Math.PI) / 180) *
      Math.cos((b[0] * Math.PI) / 180) *
      Math.cos(((b[1] - a[1]) * Math.PI) / 180);
  const brng = (Math.atan2(y, x) * 180) / Math.PI;
  return Math.round((brng + 360) % 360);
}

/** Determines if a unit is currently executing simulated movement */
export function isUnitMoving(u: Unit): boolean {
  if (u.status === "halted" || u.status === "stale") return false;
  return (u.speedKph ?? 0) > 0;
}

/** Determines unit directional heading from telemetry or recent trail trajectory */
export function getUnitHeading(u: Unit, trail?: Array<[number, number]>): number {
  if (typeof u.heading === "number" && !isNaN(u.heading) && u.heading >= 0) {
    return u.heading;
  }
  if (trail && trail.length >= 2) {
    const prev = trail[trail.length - 2]!;
    const cur = trail[trail.length - 1]!;
    return calculateBearing([prev[1], prev[0]], [cur[1], cur[0]]);
  }
  return 0;
}

/**
 * Bounded Movement Trail Buffer
 * Records authoritative simulation coordinates for rendering fade-out movement trails.
 * Strictly bounded and cleanly resettable when switching worlds or branches.
 */
export class UnitTrailBuffer {
  private trails = new Map<string, Array<[number, number]>>();
  private maxLen: number;

  constructor(maxLen = MAX_TRAIL_LENGTH) {
    this.maxLen = maxLen;
  }

  record(unitId: string, lon: number, lat: number): void {
    let list = this.trails.get(unitId);
    if (!list) {
      list = [];
      this.trails.set(unitId, list);
    }
    const last = list[list.length - 1];
    // Only append if position has updated
    if (!last || Math.abs(last[0] - lon) > 0.00001 || Math.abs(last[1] - lat) > 0.00001) {
      list.push([lon, lat]);
      if (list.length > this.maxLen) {
        list.splice(0, list.length - this.maxLen);
      }
    }
  }

  get(unitId: string): Array<[number, number]> | undefined {
    return this.trails.get(unitId);
  }

  prune(activeUnitIds: Set<string>): void {
    for (const id of this.trails.keys()) {
      if (!activeUnitIds.has(id)) {
        this.trails.delete(id);
      }
    }
  }

  clear(): void {
    this.trails.clear();
  }

  toGeoJson(selectedId?: string | null): FeatureCollection {
    const features = [];
    for (const [id, pts] of this.trails.entries()) {
      if (pts.length < 2) continue;
      const isSelected = selectedId === id;
      features.push({
        type: "Feature" as const,
        properties: {
          id,
          selected: isSelected,
          color: isSelected ? "#38BDF8" : "rgba(255, 255, 255, 0.7)",
          width: isSelected ? 2.5 : 1.5,
        },
        geometry: {
          type: "LineString" as const,
          coordinates: pts,
        },
      });
    }
    return {
      type: "FeatureCollection",
      features,
    };
  }
}
