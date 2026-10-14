export interface LiveKeyframe {
  timePct: number; // 0.0 to 1.0 (relative loop time)
  x: number; // percentage (0 to 100)
  y: number; // percentage (0 to 100)
  w: number; // percentage (0 to 100)
  h: number; // percentage (0 to 100)
  confidence?: number;
}

export interface LiveTargetTrajectory {
  id: string; // e.g. "TRK-01"
  label: string; // "vehicle" | "car" | "truck" | "person" | "airplane" | "bus" | "bicycle"
  category: "vehicle" | "person" | "aircraft" | "infrastructure";
  classification: string;
  baseConfidence: number;
  speedKmh: number;
  alertLevel: "normal" | "warning" | "critical";
  keyframes: LiveKeyframe[];
}

export interface ActiveLiveTrack {
  id: string;
  label: string;
  category: "vehicle" | "person" | "aircraft" | "infrastructure";
  classification: string;
  confidence: number;
  box: { x: number; y: number; w: number; h: number };
  velocity: { vx: number; vy: number; speedKmh: number };
  heading: number;
  alertLevel: "normal" | "warning" | "critical";
  trail: Array<{ x: number; y: number }>;
}

export interface SurveillanceVideo {
  id: string;
  channel: string;
  name: string;
  src: string;
  sector: "PERIMETER" | "TRANSIT" | "AERIAL_UAV" | "FACILITY";
  sectorLabel: string;
  sensorMode: "EO-OPTICAL" | "FLIR-THERMAL" | "NIGHT-VISION" | "GIMBAL-IR";
  alt: string;
  telemetry: {
    lat: number;
    lon: number;
    heading: number;
    status: "TRACK" | "SURVEIL" | "PATROL" | "LOCKED";
  };
  expectedTargets: string[];
  description: string;
  defaultDetections: Array<{
    label: string;
    confidence: number;
    box: { x: number; y: number; w: number; h: number };
  }>;
  dynamicTrajectories: LiveTargetTrajectory[];
}

export const SURVEILLANCE_SECTORS = [
  { id: "ALL", label: "All Sectors (24 Feeds)" },
  { id: "PERIMETER", label: "Perimeter Defense (6 Feeds)" },
  { id: "TRANSIT", label: "Convoy & Checkpoints (6 Feeds)" },
  { id: "AERIAL_UAV", label: "Aerial UAV Recon (6 Feeds)" },
  { id: "FACILITY", label: "Facility Outer & Yards (6 Feeds)" },
] as const;

export type SurveillanceSectorId = (typeof SURVEILLANCE_SECTORS)[number]["id"];

/**
 * Computes live, time-interpolated bounding boxes, velocity vectors,
 * headings, and historic trail coordinates based on active video playback time.
 */
export function computeLiveDetections(
  video: SurveillanceVideo,
  currentTime: number,
  duration?: number
): ActiveLiveTrack[] {
  if (!video.dynamicTrajectories || video.dynamicTrajectories.length === 0) {
    // Fallback to default static detections
    return (video.defaultDetections || []).map((d, i) => ({
      id: `TRK-0${i + 1}`,
      label: d.label,
      category: d.label === "person" ? "person" : "vehicle",
      classification: "Static Target",
      confidence: d.confidence,
      box: d.box,
      velocity: { vx: 0, vy: 0, speedKmh: 0 },
      heading: video.telemetry.heading,
      alertLevel: "normal",
      trail: [{ x: d.box.x + d.box.w / 2, y: d.box.y + d.box.h / 2 }],
    }));
  }

  const loopDur = duration && duration > 0.5 ? duration : 10.0;
  const rawProgress = (currentTime % loopDur) / loopDur;
  const progress = Math.max(0, Math.min(1, rawProgress));

  return video.dynamicTrajectories.map((traj) => {
    const kfs = traj.keyframes;
    if (kfs.length === 0) {
      return {
        id: traj.id,
        label: traj.label,
        category: traj.category,
        classification: traj.classification,
        confidence: traj.baseConfidence,
        box: { x: 30, y: 30, w: 20, h: 20 },
        velocity: { vx: 0, vy: 0, speedKmh: traj.speedKmh },
        heading: 0,
        alertLevel: traj.alertLevel,
        trail: [],
      };
    }

    // Helper to evaluate position at a given time percentage
    const evalAtTime = (tPct: number) => {
      const sorted = [...kfs].sort((a, b) => a.timePct - b.timePct);
      if (tPct <= sorted[0]!.timePct) return sorted[0]!;
      if (tPct >= sorted[sorted.length - 1]!.timePct) return sorted[sorted.length - 1]!;

      for (let i = 0; i < sorted.length - 1; i++) {
        const k1 = sorted[i]!;
        const k2 = sorted[i + 1]!;
        if (k1.timePct <= tPct && tPct <= k2.timePct) {
          const span = k2.timePct - k1.timePct;
          const u = span > 0 ? (tPct - k1.timePct) / span : 0;
          // Smoothstep easing for cinematic camera tracking
          const s = u * u * (3 - 2 * u);
          return {
            x: k1.x + (k2.x - k1.x) * s,
            y: k1.y + (k2.y - k1.y) * s,
            w: k1.w + (k2.w - k1.w) * s,
            h: k1.h + (k2.h - k1.h) * s,
            confidence:
              (k1.confidence ?? traj.baseConfidence) * (1 - s) +
              (k2.confidence ?? traj.baseConfidence) * s,
          };
        }
      }
      return sorted[0]!;
    };

    const currentBox = evalAtTime(progress);

    // Compute velocity vector by sampling a tiny step forward
    const dt = 0.02;
    const nextProgress = (progress + dt) % 1.0;
    const nextBox = evalAtTime(nextProgress);
    const vx = (nextBox.x - currentBox.x) / dt;
    const vy = (nextBox.y - currentBox.y) / dt;

    let heading = Math.round((Math.atan2(vy, vx) * 180) / Math.PI);
    if (heading < 0) heading += 360;
    if (Math.abs(vx) < 0.1 && Math.abs(vy) < 0.1) {
      heading = video.telemetry.heading;
    }

    // Generate recent historical trail points
    const trailSteps = [0.08, 0.05, 0.02];
    const trail = trailSteps.map((step) => {
      let pastPct = progress - step;
      if (pastPct < 0) pastPct += 1.0;
      const pt = evalAtTime(pastPct);
      return {
        x: Math.round((pt.x + pt.w / 2) * 10) / 10,
        y: Math.round((pt.y + pt.h / 2) * 10) / 10,
      };
    });

    const confVariation = Math.sin(progress * Math.PI * 4) * 0.03;
    const finalConf = Math.min(
      0.99,
      Math.max(0.6, (currentBox.confidence ?? traj.baseConfidence) + confVariation)
    );

    return {
      id: traj.id,
      label: traj.label,
      category: traj.category,
      classification: traj.classification,
      confidence: Math.round(finalConf * 100) / 100,
      box: {
        x: Math.max(1, Math.min(94, Math.round(currentBox.x * 10) / 10)),
        y: Math.max(1, Math.min(94, Math.round(currentBox.y * 10) / 10)),
        w: Math.max(4, Math.min(60, Math.round(currentBox.w * 10) / 10)),
        h: Math.max(4, Math.min(70, Math.round(currentBox.h * 10) / 10)),
      },
      velocity: {
        vx: Math.round(vx * 10) / 10,
        vy: Math.round(vy * 10) / 10,
        speedKmh: traj.speedKmh,
      },
      heading,
      alertLevel: traj.alertLevel,
      trail,
    };
  });
}

export const SURVEILLANCE_VIDEOS: SurveillanceVideo[] = [
  // =========================================================================
  // 1. Perimeter Defense (CAM-01 to CAM-06) — 100% Outdoor Tactical Surveillance
  // =========================================================================
  {
    id: "CAM-01",
    channel: "CAM-01",
    name: "Perimeter North Checkpoint Gate",
    src: "/videos/surveillance/cam-01.mp4",
    sector: "PERIMETER",
    sectorLabel: "Base Perimeter North",
    sensorMode: "EO-OPTICAL",
    alt: "12m",
    telemetry: { lat: 32.7482, lon: 74.8821, heading: 4, status: "TRACK" },
    expectedTargets: ["vehicle", "truck", "person"],
    description: "Outdoor fortified highway roadblock and incoming vehicle inspection portal.",
    defaultDetections: [
      { label: "vehicle", confidence: 0.95, box: { x: 32, y: 44, w: 22, h: 28 } },
      { label: "truck", confidence: 0.91, box: { x: 62, y: 34, w: 26, h: 36 } },
    ],
    dynamicTrajectories: [
      {
        id: "TRK-01",
        label: "vehicle",
        category: "vehicle",
        classification: "Approaching Security SUV",
        baseConfidence: 0.95,
        speedKmh: 28,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 22, y: 32, w: 16, h: 22, confidence: 0.92 },
          { timePct: 0.35, x: 34, y: 44, w: 22, h: 28, confidence: 0.96 },
          { timePct: 0.7, x: 48, y: 58, w: 26, h: 32, confidence: 0.97 },
          { timePct: 1.0, x: 22, y: 32, w: 16, h: 22, confidence: 0.92 },
        ],
      },
      {
        id: "TRK-02",
        label: "truck",
        category: "vehicle",
        classification: "Heavy Logistics Transporter",
        baseConfidence: 0.92,
        speedKmh: 18,
        alertLevel: "warning",
        keyframes: [
          { timePct: 0.0, x: 68, y: 28, w: 22, h: 30, confidence: 0.91 },
          { timePct: 0.5, x: 58, y: 40, w: 27, h: 36, confidence: 0.94 },
          { timePct: 1.0, x: 68, y: 28, w: 22, h: 30, confidence: 0.91 },
        ],
      },
      {
        id: "TRK-03",
        label: "person",
        category: "person",
        classification: "Perimeter Sentry Guard",
        baseConfidence: 0.89,
        speedKmh: 4,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 42, y: 48, w: 9, h: 22, confidence: 0.88 },
          { timePct: 0.5, x: 46, y: 52, w: 10, h: 24, confidence: 0.91 },
          { timePct: 1.0, x: 42, y: 48, w: 9, h: 22, confidence: 0.88 },
        ],
      },
    ],
  },
  {
    id: "CAM-02",
    channel: "CAM-02",
    name: "Perimeter East IR Night Vision",
    src: "/videos/surveillance/cam-02.mp4",
    sector: "PERIMETER",
    sectorLabel: "Perimeter East Fence",
    sensorMode: "NIGHT-VISION",
    alt: "15m",
    telemetry: { lat: 32.7419, lon: 74.8945, heading: 92, status: "SURVEIL" },
    expectedTargets: ["person", "vehicle", "thermal_anomaly"],
    description: "4K High-Resolution Outdoor Infrared Bullet Camera with Nighttime Perimeter View.",
    defaultDetections: [
      { label: "vehicle", confidence: 0.94, box: { x: 30, y: 46, w: 28, h: 34 } },
      { label: "person", confidence: 0.88, box: { x: 65, y: 38, w: 12, h: 32 } },
    ],
    dynamicTrajectories: [
      {
        id: "TRK-01",
        label: "vehicle",
        category: "vehicle",
        classification: "Staged Response Vehicle",
        baseConfidence: 0.94,
        speedKmh: 0,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 28, y: 44, w: 28, h: 34, confidence: 0.94 },
          { timePct: 0.5, x: 29, y: 45, w: 28, h: 34, confidence: 0.95 },
          { timePct: 1.0, x: 28, y: 44, w: 28, h: 34, confidence: 0.94 },
        ],
      },
      {
        id: "TRK-02",
        label: "person",
        category: "person",
        classification: "Night Security Patrol",
        baseConfidence: 0.89,
        speedKmh: 5,
        alertLevel: "warning",
        keyframes: [
          { timePct: 0.0, x: 74, y: 32, w: 11, h: 30, confidence: 0.86 },
          { timePct: 0.45, x: 64, y: 44, w: 13, h: 34, confidence: 0.92 },
          { timePct: 0.85, x: 54, y: 56, w: 14, h: 38, confidence: 0.91 },
          { timePct: 1.0, x: 74, y: 32, w: 11, h: 30, confidence: 0.86 },
        ],
      },
    ],
  },
  {
    id: "CAM-03",
    channel: "CAM-03",
    name: "Outer Staging Ground & Barrier",
    src: "/videos/surveillance/cam-03.mp4",
    sector: "PERIMETER",
    sectorLabel: "Staging Barrier Sector 3",
    sensorMode: "EO-OPTICAL",
    alt: "18m",
    telemetry: { lat: 32.7351, lon: 74.8712, heading: 215, status: "LOCKED" },
    expectedTargets: ["vehicle", "truck", "barrier"],
    description: "Outdoor multi-lane vehicle staging buffer and defensive berm approach.",
    defaultDetections: [
      { label: "vehicle", confidence: 0.93, box: { x: 24, y: 38, w: 24, h: 26 } },
      { label: "bus", confidence: 0.9, box: { x: 56, y: 30, w: 28, h: 34 } },
    ],
    dynamicTrajectories: [
      {
        id: "TRK-01",
        label: "vehicle",
        category: "vehicle",
        classification: "Personnel Carrier",
        baseConfidence: 0.93,
        speedKmh: 22,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 18, y: 32, w: 20, h: 24, confidence: 0.91 },
          { timePct: 0.5, x: 30, y: 44, w: 24, h: 28, confidence: 0.95 },
          { timePct: 1.0, x: 18, y: 32, w: 20, h: 24, confidence: 0.91 },
        ],
      },
      {
        id: "TRK-02",
        label: "bus",
        category: "vehicle",
        classification: "Troop Transport Bus",
        baseConfidence: 0.91,
        speedKmh: 14,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 62, y: 26, w: 25, h: 30, confidence: 0.9 },
          { timePct: 0.5, x: 52, y: 36, w: 28, h: 35, confidence: 0.93 },
          { timePct: 1.0, x: 62, y: 26, w: 25, h: 30, confidence: 0.9 },
        ],
      },
    ],
  },
  {
    id: "CAM-04",
    channel: "CAM-04",
    name: "Forward Observation Post Alpha",
    src: "/videos/surveillance/cam-04.mp4",
    sector: "PERIMETER",
    sectorLabel: "FOB Alpha Intersection",
    sensorMode: "EO-OPTICAL",
    alt: "16m",
    telemetry: { lat: 32.7562, lon: 74.8643, heading: 310, status: "SURVEIL" },
    expectedTargets: ["person", "car", "bicycle"],
    description: "Elevated outdoor security vantage point monitoring vehicle and personnel crossroads.",
    defaultDetections: [
      { label: "car", confidence: 0.94, box: { x: 38, y: 32, w: 28, h: 36 } },
      { label: "person", confidence: 0.89, box: { x: 18, y: 42, w: 12, h: 38 } },
    ],
    dynamicTrajectories: [
      {
        id: "TRK-01",
        label: "car",
        category: "vehicle",
        classification: "Civilian Liaison Sedan",
        baseConfidence: 0.95,
        speedKmh: 35,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 22, y: 55, w: 22, h: 30, confidence: 0.92 },
          { timePct: 0.5, x: 44, y: 38, w: 26, h: 34, confidence: 0.96 },
          { timePct: 1.0, x: 22, y: 55, w: 22, h: 30, confidence: 0.92 },
        ],
      },
      {
        id: "TRK-02",
        label: "person",
        category: "person",
        classification: "Stationed Spotter",
        baseConfidence: 0.9,
        speedKmh: 3,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 16, y: 40, w: 10, h: 36, confidence: 0.88 },
          { timePct: 0.5, x: 18, y: 42, w: 11, h: 37, confidence: 0.91 },
          { timePct: 1.0, x: 16, y: 40, w: 10, h: 36, confidence: 0.88 },
        ],
      },
    ],
  },
  {
    id: "CAM-05",
    channel: "CAM-05",
    name: "North Berm Vehicle Sentry",
    src: "/videos/surveillance/cam-05.mp4",
    sector: "PERIMETER",
    sectorLabel: "North Berm Exclusion",
    sensorMode: "FLIR-THERMAL",
    alt: "10m",
    telemetry: { lat: 32.7612, lon: 74.8791, heading: 15, status: "TRACK" },
    expectedTargets: ["vehicle", "truck", "person"],
    description: "Thermal and optical checkpoint at outer defensive embankment.",
    defaultDetections: [
      { label: "vehicle", confidence: 0.93, box: { x: 35, y: 42, w: 24, h: 28 } },
      { label: "truck", confidence: 0.89, box: { x: 62, y: 32, w: 28, h: 38 } },
    ],
    dynamicTrajectories: [
      {
        id: "TRK-01",
        label: "vehicle",
        category: "vehicle",
        classification: "Perimeter Interceptor Unit",
        baseConfidence: 0.93,
        speedKmh: 30,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 25, y: 35, w: 18, h: 24, confidence: 0.91 },
          { timePct: 0.5, x: 42, y: 52, w: 24, h: 30, confidence: 0.95 },
          { timePct: 1.0, x: 25, y: 35, w: 18, h: 24, confidence: 0.91 },
        ],
      },
      {
        id: "TRK-02",
        label: "truck",
        category: "vehicle",
        classification: "Tactical Supply Hauler",
        baseConfidence: 0.9,
        speedKmh: 16,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 65, y: 30, w: 25, h: 34, confidence: 0.89 },
          { timePct: 0.5, x: 55, y: 44, w: 28, h: 38, confidence: 0.92 },
          { timePct: 1.0, x: 65, y: 30, w: 25, h: 34, confidence: 0.89 },
        ],
      },
    ],
  },
  {
    id: "CAM-06",
    channel: "CAM-06",
    name: "Perimeter South Night Patrol",
    src: "/videos/surveillance/cam-06.mp4",
    sector: "PERIMETER",
    sectorLabel: "Access Gate Sally Port",
    sensorMode: "NIGHT-VISION",
    alt: "14m",
    telemetry: { lat: 32.7441, lon: 74.8804, heading: 180, status: "LOCKED" },
    expectedTargets: ["vehicle", "person", "thermal_anomaly"],
    description: "Reinforced south gate night vision camera tracking outer barbed perimeter.",
    defaultDetections: [
      { label: "vehicle", confidence: 0.96, box: { x: 30, y: 45, w: 32, h: 36 } },
      { label: "person", confidence: 0.9, box: { x: 66, y: 36, w: 13, h: 34 } },
    ],
    dynamicTrajectories: [
      {
        id: "TRK-01",
        label: "vehicle",
        category: "vehicle",
        classification: "Armored Guard Carrier",
        baseConfidence: 0.96,
        speedKmh: 0,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 30, y: 45, w: 32, h: 36, confidence: 0.96 },
          { timePct: 0.5, x: 31, y: 46, w: 32, h: 36, confidence: 0.96 },
          { timePct: 1.0, x: 30, y: 45, w: 32, h: 36, confidence: 0.96 },
        ],
      },
      {
        id: "TRK-02",
        label: "person",
        category: "person",
        classification: "Perimeter Foot Guard",
        baseConfidence: 0.91,
        speedKmh: 6,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 72, y: 30, w: 11, h: 30, confidence: 0.88 },
          { timePct: 0.5, x: 60, y: 46, w: 14, h: 36, confidence: 0.93 },
          { timePct: 1.0, x: 72, y: 30, w: 11, h: 30, confidence: 0.88 },
        ],
      },
    ],
  },

  // =========================================================================
  // 2. Convoy & Transit Checkpoints (CAM-07 to CAM-12)
  // =========================================================================
  {
    id: "CAM-07",
    channel: "CAM-07",
    name: "MSR Iron Highway Gantry",
    src: "/videos/surveillance/cam-07.mp4",
    sector: "TRANSIT",
    sectorLabel: "Main Supply Route (MSR)",
    sensorMode: "EO-OPTICAL",
    alt: "14m",
    telemetry: { lat: 32.7214, lon: 74.8521, heading: 135, status: "PATROL" },
    expectedTargets: ["car", "truck", "convoy"],
    description: "High-capacity overhead gantry surveillance on primary 4-lane paved supply corridor.",
    defaultDetections: [
      { label: "car", confidence: 0.96, box: { x: 22, y: 36, w: 26, h: 30 } },
      { label: "truck", confidence: 0.92, box: { x: 54, y: 26, w: 32, h: 42 } },
    ],
    dynamicTrajectories: [
      {
        id: "TRK-01",
        label: "car",
        category: "vehicle",
        classification: "Westbound Convoy Lead",
        baseConfidence: 0.96,
        speedKmh: 68,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 12, y: 52, w: 22, h: 26, confidence: 0.94 },
          { timePct: 0.45, x: 35, y: 38, w: 26, h: 30, confidence: 0.97 },
          { timePct: 0.9, x: 58, y: 22, w: 28, h: 32, confidence: 0.96 },
          { timePct: 1.0, x: 12, y: 52, w: 22, h: 26, confidence: 0.94 },
        ],
      },
      {
        id: "TRK-02",
        label: "truck",
        category: "vehicle",
        classification: "Heavy Freight Semitrailer",
        baseConfidence: 0.93,
        speedKmh: 54,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 72, y: 20, w: 28, h: 36, confidence: 0.92 },
          { timePct: 0.5, x: 48, y: 36, w: 32, h: 42, confidence: 0.95 },
          { timePct: 1.0, x: 72, y: 20, w: 28, h: 36, confidence: 0.92 },
        ],
      },
    ],
  },
  {
    id: "CAM-08",
    channel: "CAM-08",
    name: "Tactical Checkpoint Bravo",
    src: "/videos/surveillance/cam-08.mp4",
    sector: "TRANSIT",
    sectorLabel: "Checkpoint Bravo Arterial",
    sensorMode: "EO-OPTICAL",
    alt: "12m",
    telemetry: { lat: 32.7298, lon: 74.8605, heading: 45, status: "TRACK" },
    expectedTargets: ["person", "car", "bicycle"],
    description: "Multi-lane verification crossroads monitoring civilian and tactical traffic flow.",
    defaultDetections: [
      { label: "car", confidence: 0.93, box: { x: 38, y: 32, w: 30, h: 38 } },
      { label: "person", confidence: 0.91, box: { x: 18, y: 40, w: 12, h: 42 } },
    ],
    dynamicTrajectories: [
      {
        id: "TRK-01",
        label: "car",
        category: "vehicle",
        classification: "Highway Patrol Cruiser",
        baseConfidence: 0.94,
        speedKmh: 42,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 18, y: 62, w: 24, h: 32, confidence: 0.91 },
          { timePct: 0.5, x: 45, y: 35, w: 28, h: 36, confidence: 0.95 },
          { timePct: 1.0, x: 18, y: 62, w: 24, h: 32, confidence: 0.91 },
        ],
      },
      {
        id: "TRK-02",
        label: "person",
        category: "person",
        classification: "Checkpoint Inspector",
        baseConfidence: 0.91,
        speedKmh: 4,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 15, y: 38, w: 10, h: 40, confidence: 0.89 },
          { timePct: 0.5, x: 22, y: 42, w: 12, h: 42, confidence: 0.92 },
          { timePct: 1.0, x: 15, y: 38, w: 10, h: 40, confidence: 0.89 },
        ],
      },
    ],
  },
  {
    id: "CAM-09",
    channel: "CAM-09",
    name: "Sector 4 Express Corridor",
    src: "/videos/surveillance/cam-09.mp4",
    sector: "TRANSIT",
    sectorLabel: "Transit Corridor Sector 4",
    sensorMode: "EO-OPTICAL",
    alt: "16m",
    telemetry: { lat: 32.7381, lon: 74.8692, heading: 88, status: "SURVEIL" },
    expectedTargets: ["car", "vehicle", "traffic_stream"],
    description: "Automated road surveillance tracking oncoming and passing vehicles in real-time.",
    defaultDetections: [
      { label: "car", confidence: 0.95, box: { x: 26, y: 42, w: 26, h: 28 } },
      { label: "car", confidence: 0.91, box: { x: 56, y: 40, w: 22, h: 25 } },
    ],
    dynamicTrajectories: [
      {
        id: "TRK-01",
        label: "car",
        category: "vehicle",
        classification: "Approaching Transport",
        baseConfidence: 0.96,
        speedKmh: 58,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 38, y: 36, w: 16, h: 18, confidence: 0.92 },
          { timePct: 0.5, x: 24, y: 46, w: 26, h: 28, confidence: 0.96 },
          { timePct: 0.95, x: 10, y: 60, w: 34, h: 36, confidence: 0.97 },
          { timePct: 1.0, x: 38, y: 36, w: 16, h: 18, confidence: 0.92 },
        ],
      },
      {
        id: "TRK-02",
        label: "car",
        category: "vehicle",
        classification: "Preceding Civilian Vehicle",
        baseConfidence: 0.93,
        speedKmh: 52,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 52, y: 38, w: 18, h: 22, confidence: 0.91 },
          { timePct: 0.5, x: 58, y: 42, w: 22, h: 26, confidence: 0.94 },
          { timePct: 1.0, x: 52, y: 38, w: 18, h: 22, confidence: 0.91 },
        ],
      },
    ],
  },
  {
    id: "CAM-10",
    channel: "CAM-10",
    name: "Heavy Transport Weigh Station",
    src: "/videos/surveillance/cam-10.mp4",
    sector: "TRANSIT",
    sectorLabel: "Depot Access Weigh Station",
    sensorMode: "EO-OPTICAL",
    alt: "10m",
    telemetry: { lat: 32.7155, lon: 74.8784, heading: 270, status: "PATROL" },
    expectedTargets: ["truck", "vehicle", "cargo_container"],
    description: "Inspection gantry and axle scales verifying manifest weights for heavy armor haulers.",
    defaultDetections: [
      { label: "truck", confidence: 0.94, box: { x: 35, y: 38, w: 28, h: 35 } },
      { label: "vehicle", confidence: 0.9, box: { x: 65, y: 32, w: 20, h: 26 } },
    ],
    dynamicTrajectories: [
      {
        id: "TRK-01",
        label: "truck",
        category: "vehicle",
        classification: "Articulated Munitions Hauler",
        baseConfidence: 0.94,
        speedKmh: 20,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 26, y: 30, w: 22, h: 28, confidence: 0.92 },
          { timePct: 0.5, x: 38, y: 44, w: 28, h: 36, confidence: 0.95 },
          { timePct: 1.0, x: 26, y: 30, w: 22, h: 28, confidence: 0.92 },
        ],
      },
      {
        id: "TRK-02",
        label: "vehicle",
        category: "vehicle",
        classification: "Escort Security Pick-up",
        baseConfidence: 0.91,
        speedKmh: 25,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 68, y: 26, w: 18, h: 22, confidence: 0.89 },
          { timePct: 0.5, x: 60, y: 36, w: 22, h: 28, confidence: 0.92 },
          { timePct: 1.0, x: 68, y: 26, w: 18, h: 22, confidence: 0.89 },
        ],
      },
    ],
  },
  {
    id: "CAM-11",
    channel: "CAM-11",
    name: "Southern Supply Arterial",
    src: "/videos/surveillance/cam-11.mp4",
    sector: "TRANSIT",
    sectorLabel: "Southern Supply Arterial",
    sensorMode: "FLIR-THERMAL",
    alt: "12m",
    telemetry: { lat: 32.7121, lon: 74.8839, heading: 195, status: "LOCKED" },
    expectedTargets: ["car", "truck", "convoy"],
    description: "Dual-lane arterial corridor connecting southern staging hubs to frontline nodes.",
    defaultDetections: [
      { label: "car", confidence: 0.95, box: { x: 20, y: 42, w: 25, h: 30 } },
      { label: "truck", confidence: 0.92, box: { x: 55, y: 30, w: 30, h: 40 } },
    ],
    dynamicTrajectories: [
      {
        id: "TRK-01",
        label: "car",
        category: "vehicle",
        classification: "Staff Reconnaissance Car",
        baseConfidence: 0.95,
        speedKmh: 60,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 14, y: 56, w: 22, h: 28, confidence: 0.93 },
          { timePct: 0.5, x: 36, y: 40, w: 25, h: 30, confidence: 0.96 },
          { timePct: 1.0, x: 14, y: 56, w: 22, h: 28, confidence: 0.93 },
        ],
      },
      {
        id: "TRK-02",
        label: "truck",
        category: "vehicle",
        classification: "Containerized Hauler",
        baseConfidence: 0.92,
        speedKmh: 48,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 68, y: 24, w: 26, h: 34, confidence: 0.9 },
          { timePct: 0.5, x: 48, y: 38, w: 32, h: 42, confidence: 0.94 },
          { timePct: 1.0, x: 68, y: 24, w: 26, h: 34, confidence: 0.9 },
        ],
      },
    ],
  },
  {
    id: "CAM-12",
    channel: "CAM-12",
    name: "Forward Reconnaissance Route",
    src: "/videos/surveillance/cam-12.mp4",
    sector: "TRANSIT",
    sectorLabel: "Forward Recon Route",
    sensorMode: "EO-OPTICAL",
    alt: "15m",
    telemetry: { lat: 32.7088, lon: 74.8912, heading: 330, status: "SURVEIL" },
    expectedTargets: ["car", "vehicle", "patrol"],
    description: "Long-range tactical optical camera scanning outer highway approach for hostile assets.",
    defaultDetections: [
      { label: "car", confidence: 0.94, box: { x: 32, y: 44, w: 24, h: 26 } },
      { label: "car", confidence: 0.89, box: { x: 60, y: 38, w: 20, h: 22 } },
    ],
    dynamicTrajectories: [
      {
        id: "TRK-01",
        label: "car",
        category: "vehicle",
        classification: "Lead Escort Vehicle",
        baseConfidence: 0.94,
        speedKmh: 64,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 42, y: 34, w: 15, h: 18, confidence: 0.9 },
          { timePct: 0.5, x: 28, y: 48, w: 26, h: 28, confidence: 0.95 },
          { timePct: 1.0, x: 42, y: 34, w: 15, h: 18, confidence: 0.9 },
        ],
      },
      {
        id: "TRK-02",
        label: "car",
        category: "vehicle",
        classification: "Rear Escort Vehicle",
        baseConfidence: 0.9,
        speedKmh: 62,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 55, y: 36, w: 18, h: 20, confidence: 0.88 },
          { timePct: 0.5, x: 62, y: 42, w: 22, h: 24, confidence: 0.92 },
          { timePct: 1.0, x: 55, y: 36, w: 18, h: 20, confidence: 0.88 },
        ],
      },
    ],
  },

  // =========================================================================
  // 3. Aerial & Airfield Overwatch (CAM-13 to CAM-18)
  // =========================================================================
  {
    id: "CAM-13",
    channel: "CAM-13",
    name: "Airfield Runway Alpha Recon",
    src: "/videos/surveillance/cam-13.mp4",
    sector: "AERIAL_UAV",
    sectorLabel: "Tactical Airfield Alpha",
    sensorMode: "EO-OPTICAL",
    alt: "45m",
    telemetry: { lat: 32.7824, lon: 74.8415, heading: 24, status: "TRACK" },
    expectedTargets: ["airplane", "truck", "person"],
    description: "Primary outdoor runway and tarmac camera tracking aircraft taxiing and ground equipment.",
    defaultDetections: [
      { label: "airplane", confidence: 0.97, box: { x: 25, y: 28, w: 38, h: 26 } },
      { label: "truck", confidence: 0.92, box: { x: 62, y: 48, w: 20, h: 24 } },
      { label: "person", confidence: 0.88, box: { x: 52, y: 52, w: 8, h: 20 } },
    ],
    dynamicTrajectories: [
      {
        id: "TRK-01",
        label: "airplane",
        category: "aircraft",
        classification: "Taxiing Airlifter C-130",
        baseConfidence: 0.98,
        speedKmh: 24,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 18, y: 24, w: 32, h: 24, confidence: 0.96 },
          { timePct: 0.5, x: 30, y: 30, w: 40, h: 28, confidence: 0.98 },
          { timePct: 1.0, x: 18, y: 24, w: 32, h: 24, confidence: 0.96 },
        ],
      },
      {
        id: "TRK-02",
        label: "truck",
        category: "vehicle",
        classification: "Airfield Tarmac Tug",
        baseConfidence: 0.92,
        speedKmh: 15,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 68, y: 44, w: 18, h: 22, confidence: 0.9 },
          { timePct: 0.5, x: 58, y: 50, w: 22, h: 26, confidence: 0.94 },
          { timePct: 1.0, x: 68, y: 44, w: 18, h: 22, confidence: 0.9 },
        ],
      },
      {
        id: "TRK-03",
        label: "person",
        category: "person",
        classification: "Ground Flight Marshaller",
        baseConfidence: 0.89,
        speedKmh: 3,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 50, y: 50, w: 7, h: 18, confidence: 0.87 },
          { timePct: 0.5, x: 54, y: 54, w: 8, h: 20, confidence: 0.91 },
          { timePct: 1.0, x: 50, y: 50, w: 7, h: 18, confidence: 0.87 },
        ],
      },
    ],
  },
  {
    id: "CAM-14",
    channel: "CAM-14",
    name: "Tactical Apron & Taxiway Overwatch",
    src: "/videos/surveillance/cam-14.mp4",
    sector: "AERIAL_UAV",
    sectorLabel: "Apron Overwatch",
    sensorMode: "EO-OPTICAL",
    alt: "38m",
    telemetry: { lat: 32.7691, lon: 74.8298, heading: 160, status: "PATROL" },
    expectedTargets: ["airplane", "bus", "truck"],
    description: "Elevated tower feed monitoring aircraft staging apron and rapid reaction transports.",
    defaultDetections: [
      { label: "airplane", confidence: 0.96, box: { x: 22, y: 26, w: 36, h: 28 } },
      { label: "bus", confidence: 0.91, box: { x: 64, y: 46, w: 22, h: 26 } },
    ],
    dynamicTrajectories: [
      {
        id: "TRK-01",
        label: "airplane",
        category: "aircraft",
        classification: "Staged Tactical Transport",
        baseConfidence: 0.96,
        speedKmh: 12,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 20, y: 24, w: 34, h: 26, confidence: 0.95 },
          { timePct: 0.5, x: 28, y: 28, w: 38, h: 29, confidence: 0.97 },
          { timePct: 1.0, x: 20, y: 24, w: 34, h: 26, confidence: 0.95 },
        ],
      },
      {
        id: "TRK-02",
        label: "bus",
        category: "vehicle",
        classification: "Airfield Crew Shuttle",
        baseConfidence: 0.92,
        speedKmh: 18,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 70, y: 42, w: 20, h: 24, confidence: 0.9 },
          { timePct: 0.5, x: 58, y: 48, w: 24, h: 28, confidence: 0.93 },
          { timePct: 1.0, x: 70, y: 42, w: 20, h: 24, confidence: 0.9 },
        ],
      },
    ],
  },
  {
    id: "CAM-15",
    channel: "CAM-15",
    name: "Aerial FLIR Thermal Grid",
    src: "/videos/surveillance/cam-15.mp4",
    sector: "AERIAL_UAV",
    sectorLabel: "Aerial Thermal Grid",
    sensorMode: "FLIR-THERMAL",
    alt: "520m",
    telemetry: { lat: 32.7915, lon: 74.8592, heading: 78, status: "TRACK" },
    expectedTargets: ["person", "patrol_element", "thermal_hotspot"],
    description: "Wide-area FLIR sensor array monitoring personnel movements and perimeter security.",
    defaultDetections: [
      { label: "person", confidence: 0.95, box: { x: 30, y: 30, w: 14, h: 40 } },
      { label: "person", confidence: 0.91, box: { x: 52, y: 34, w: 14, h: 42 } },
    ],
    dynamicTrajectories: [
      {
        id: "TRK-01",
        label: "person",
        category: "person",
        classification: "Patrol Element Alpha",
        baseConfidence: 0.95,
        speedKmh: 6,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 26, y: 26, w: 13, h: 38, confidence: 0.93 },
          { timePct: 0.5, x: 38, y: 38, w: 15, h: 42, confidence: 0.96 },
          { timePct: 1.0, x: 26, y: 26, w: 13, h: 38, confidence: 0.93 },
        ],
      },
      {
        id: "TRK-02",
        label: "person",
        category: "person",
        classification: "Patrol Element Bravo",
        baseConfidence: 0.92,
        speedKmh: 5,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 58, y: 30, w: 13, h: 39, confidence: 0.9 },
          { timePct: 0.5, x: 48, y: 40, w: 15, h: 44, confidence: 0.93 },
          { timePct: 1.0, x: 58, y: 30, w: 13, h: 39, confidence: 0.9 },
        ],
      },
    ],
  },
  {
    id: "CAM-16",
    channel: "CAM-16",
    name: "Sector 7 UAV Orbit",
    src: "/videos/surveillance/cam-16.mp4",
    sector: "AERIAL_UAV",
    sectorLabel: "Sector 7 UAV Orbit",
    sensorMode: "EO-OPTICAL",
    alt: "290m",
    telemetry: { lat: 32.7533, lon: 74.9102, heading: 290, status: "SURVEIL" },
    expectedTargets: ["person", "boundary_breach"],
    description: "Automated UAV patrol inspecting boundary fence integrity and approach routes.",
    defaultDetections: [
      { label: "person", confidence: 0.93, box: { x: 44, y: 25, w: 16, h: 50 } },
    ],
    dynamicTrajectories: [
      {
        id: "TRK-01",
        label: "person",
        category: "person",
        classification: "Perimeter Sweep Sentry",
        baseConfidence: 0.94,
        speedKmh: 4,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 40, y: 20, w: 15, h: 46, confidence: 0.91 },
          { timePct: 0.5, x: 48, y: 32, w: 17, h: 52, confidence: 0.95 },
          { timePct: 1.0, x: 40, y: 20, w: 15, h: 46, confidence: 0.91 },
        ],
      },
    ],
  },
  {
    id: "CAM-17",
    channel: "CAM-17",
    name: "Plaza Outer Recon Gimbal",
    src: "/videos/surveillance/cam-17.mp4",
    sector: "AERIAL_UAV",
    sectorLabel: "Plaza Recon Gimbal",
    sensorMode: "GIMBAL-IR",
    alt: "340m",
    telemetry: { lat: 32.7601, lon: 74.8344, heading: 110, status: "LOCKED" },
    expectedTargets: ["person", "movement_cluster"],
    description: "Stabilized 3-axis gyro optical pod monitoring open staging concourse.",
    defaultDetections: [
      { label: "person", confidence: 0.92, box: { x: 34, y: 38, w: 14, h: 38 } },
      { label: "person", confidence: 0.88, box: { x: 58, y: 32, w: 13, h: 36 } },
    ],
    dynamicTrajectories: [
      {
        id: "TRK-01",
        label: "person",
        category: "person",
        classification: "Patrol Officer Alpha",
        baseConfidence: 0.92,
        speedKmh: 5,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 28, y: 44, w: 13, h: 36, confidence: 0.9 },
          { timePct: 0.5, x: 42, y: 32, w: 15, h: 40, confidence: 0.94 },
          { timePct: 1.0, x: 28, y: 44, w: 13, h: 36, confidence: 0.9 },
        ],
      },
      {
        id: "TRK-02",
        label: "person",
        category: "person",
        classification: "Patrol Officer Bravo",
        baseConfidence: 0.89,
        speedKmh: 4,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 62, y: 28, w: 12, h: 34, confidence: 0.87 },
          { timePct: 0.5, x: 52, y: 40, w: 14, h: 38, confidence: 0.91 },
          { timePct: 1.0, x: 62, y: 28, w: 12, h: 34, confidence: 0.87 },
        ],
      },
    ],
  },
  {
    id: "CAM-18",
    channel: "CAM-18",
    name: "Airfield Outer Perimeter Sweep",
    src: "/videos/surveillance/cam-18.mp4",
    sector: "AERIAL_UAV",
    sectorLabel: "Airfield Outer Perimeter",
    sensorMode: "EO-OPTICAL",
    alt: "50m",
    telemetry: { lat: 32.7455, lon: 74.8622, heading: 0, status: "SURVEIL" },
    expectedTargets: ["airplane", "truck", "ground_vehicle"],
    description: "High-angle surveillance of northern runway taxiway intersection.",
    defaultDetections: [
      { label: "airplane", confidence: 0.96, box: { x: 24, y: 26, w: 38, h: 28 } },
      { label: "truck", confidence: 0.91, box: { x: 64, y: 46, w: 22, h: 24 } },
    ],
    dynamicTrajectories: [
      {
        id: "TRK-01",
        label: "airplane",
        category: "aircraft",
        classification: "Chartered Evac Transport",
        baseConfidence: 0.96,
        speedKmh: 20,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 20, y: 24, w: 34, h: 26, confidence: 0.94 },
          { timePct: 0.5, x: 30, y: 30, w: 40, h: 30, confidence: 0.97 },
          { timePct: 1.0, x: 20, y: 24, w: 34, h: 26, confidence: 0.94 },
        ],
      },
      {
        id: "TRK-02",
        label: "truck",
        category: "vehicle",
        classification: "Ramp Safety Tender",
        baseConfidence: 0.92,
        speedKmh: 14,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 68, y: 42, w: 20, h: 22, confidence: 0.9 },
          { timePct: 0.5, x: 58, y: 50, w: 24, h: 26, confidence: 0.93 },
          { timePct: 1.0, x: 68, y: 42, w: 20, h: 22, confidence: 0.9 },
        ],
      },
    ],
  },

  // =========================================================================
  // 4. Facility Outer Perimeter & Logistics Yards (CAM-19 to CAM-24)
  // =========================================================================
  {
    id: "CAM-19",
    channel: "CAM-19",
    name: "Depot Perimeter Logistics Bay",
    src: "/videos/surveillance/cam-19.mp4",
    sector: "FACILITY",
    sectorLabel: "Logistics Yard Bay 1",
    sensorMode: "EO-OPTICAL",
    alt: "12m",
    telemetry: { lat: 32.7422, lon: 74.8778, heading: 180, status: "TRACK" },
    expectedTargets: ["person", "worker", "safety_gear"],
    description: "External freight logistics staging area with real-time personnel activity tracking.",
    defaultDetections: [
      { label: "person", confidence: 0.97, box: { x: 35, y: 20, w: 22, h: 65 } },
    ],
    dynamicTrajectories: [
      {
        id: "TRK-01",
        label: "person",
        category: "person",
        classification: "Logistics Lead Inspector",
        baseConfidence: 0.97,
        speedKmh: 4,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 30, y: 18, w: 20, h: 62, confidence: 0.95 },
          { timePct: 0.5, x: 42, y: 26, w: 24, h: 68, confidence: 0.98 },
          { timePct: 1.0, x: 30, y: 18, w: 20, h: 62, confidence: 0.95 },
        ],
      },
    ],
  },
  {
    id: "CAM-20",
    channel: "CAM-20",
    name: "Heavy Freight Railhead & Depot",
    src: "/videos/surveillance/cam-20.mp4",
    sector: "FACILITY",
    sectorLabel: "Railhead Transfer Depot",
    sensorMode: "EO-OPTICAL",
    alt: "14m",
    telemetry: { lat: 32.7411, lon: 74.8765, heading: 90, status: "LOCKED" },
    expectedTargets: ["truck", "container", "freight_hauler"],
    description: "Intermodal rail and road transfer yard for heavy containerized materiel.",
    defaultDetections: [
      { label: "truck", confidence: 0.95, box: { x: 32, y: 35, w: 32, h: 38 } },
      { label: "person", confidence: 0.89, box: { x: 68, y: 42, w: 11, h: 28 } },
    ],
    dynamicTrajectories: [
      {
        id: "TRK-01",
        label: "truck",
        category: "vehicle",
        classification: "Freight Container Truck",
        baseConfidence: 0.95,
        speedKmh: 18,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 25, y: 30, w: 28, h: 34, confidence: 0.93 },
          { timePct: 0.5, x: 38, y: 40, w: 34, h: 42, confidence: 0.96 },
          { timePct: 1.0, x: 25, y: 30, w: 28, h: 34, confidence: 0.93 },
        ],
      },
      {
        id: "TRK-02",
        label: "person",
        category: "person",
        classification: "Depot Switchman",
        baseConfidence: 0.9,
        speedKmh: 3,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 65, y: 38, w: 10, h: 26, confidence: 0.88 },
          { timePct: 0.5, x: 72, y: 46, w: 12, h: 30, confidence: 0.92 },
          { timePct: 1.0, x: 65, y: 38, w: 10, h: 26, confidence: 0.88 },
        ],
      },
    ],
  },
  {
    id: "CAM-21",
    channel: "CAM-21",
    name: "Motor Pool & Vehicle Yard",
    src: "/videos/surveillance/cam-21.mp4",
    sector: "FACILITY",
    sectorLabel: "Tactical Motor Pool",
    sensorMode: "FLIR-THERMAL",
    alt: "16m",
    telemetry: { lat: 32.7435, lon: 74.8792, heading: 270, status: "SURVEIL" },
    expectedTargets: ["vehicle", "bus", "truck"],
    description: "Thermal monitoring of maintenance bays, armored motor pool, and fleet parking.",
    defaultDetections: [
      { label: "bus", confidence: 0.94, box: { x: 25, y: 32, w: 28, h: 34 } },
      { label: "vehicle", confidence: 0.91, box: { x: 60, y: 36, w: 24, h: 28 } },
    ],
    dynamicTrajectories: [
      {
        id: "TRK-01",
        label: "bus",
        category: "vehicle",
        classification: "Armored Troop Carrier",
        baseConfidence: 0.94,
        speedKmh: 12,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 22, y: 28, w: 26, h: 32, confidence: 0.92 },
          { timePct: 0.5, x: 30, y: 38, w: 30, h: 36, confidence: 0.95 },
          { timePct: 1.0, x: 22, y: 28, w: 26, h: 32, confidence: 0.92 },
        ],
      },
      {
        id: "TRK-02",
        label: "vehicle",
        category: "vehicle",
        classification: "Field Maintenance Rig",
        baseConfidence: 0.91,
        speedKmh: 16,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 65, y: 32, w: 22, h: 26, confidence: 0.89 },
          { timePct: 0.5, x: 55, y: 42, w: 26, h: 30, confidence: 0.93 },
          { timePct: 1.0, x: 65, y: 32, w: 22, h: 26, confidence: 0.89 },
        ],
      },
    ],
  },
  {
    id: "CAM-22",
    channel: "CAM-22",
    name: "Command Outer Staging Plaza",
    src: "/videos/surveillance/cam-22.mp4",
    sector: "FACILITY",
    sectorLabel: "HQ Outer Staging Plaza",
    sensorMode: "EO-OPTICAL",
    alt: "18m",
    telemetry: { lat: 32.7398, lon: 74.8741, heading: 0, status: "PATROL" },
    expectedTargets: ["person", "staff", "escort"],
    description: "Pedestrian concourse and vehicle arrival loop for Headquarters complex.",
    defaultDetections: [
      { label: "person", confidence: 0.95, box: { x: 32, y: 34, w: 15, h: 42 } },
      { label: "person", confidence: 0.9, box: { x: 62, y: 30, w: 14, h: 38 } },
    ],
    dynamicTrajectories: [
      {
        id: "TRK-01",
        label: "person",
        category: "person",
        classification: "HQ Security Officer",
        baseConfidence: 0.95,
        speedKmh: 5,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 26, y: 40, w: 14, h: 40, confidence: 0.93 },
          { timePct: 0.5, x: 40, y: 28, w: 16, h: 44, confidence: 0.96 },
          { timePct: 1.0, x: 26, y: 40, w: 14, h: 40, confidence: 0.93 },
        ],
      },
      {
        id: "TRK-02",
        label: "person",
        category: "person",
        classification: "Staff Aide Escort",
        baseConfidence: 0.91,
        speedKmh: 4,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 66, y: 26, w: 13, h: 36, confidence: 0.89 },
          { timePct: 0.5, x: 56, y: 38, w: 15, h: 40, confidence: 0.93 },
          { timePct: 1.0, x: 66, y: 26, w: 13, h: 36, confidence: 0.89 },
        ],
      },
    ],
  },
  {
    id: "CAM-23",
    channel: "CAM-23",
    name: "Munitions Depot Outer Yard",
    src: "/videos/surveillance/cam-23.mp4",
    sector: "FACILITY",
    sectorLabel: "Munitions Depot Outer",
    sensorMode: "EO-OPTICAL",
    alt: "15m",
    telemetry: { lat: 32.7445, lon: 74.8819, heading: 180, status: "TRACK" },
    expectedTargets: ["person", "barrier", "perimeter_sentry"],
    description: "Reinforced blast-defilade apron outside high-explosive ammunition storage.",
    defaultDetections: [
      { label: "person", confidence: 0.96, box: { x: 38, y: 22, w: 20, h: 64 } },
    ],
    dynamicTrajectories: [
      {
        id: "TRK-01",
        label: "person",
        category: "person",
        classification: "Munitions Yard Sentry",
        baseConfidence: 0.96,
        speedKmh: 4,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 34, y: 18, w: 18, h: 60, confidence: 0.94 },
          { timePct: 0.5, x: 44, y: 28, w: 22, h: 68, confidence: 0.97 },
          { timePct: 1.0, x: 34, y: 18, w: 18, h: 60, confidence: 0.94 },
        ],
      },
    ],
  },
  {
    id: "CAM-24",
    channel: "CAM-24",
    name: "Fuel Depot Staging Ramp",
    src: "/videos/surveillance/cam-24.mp4",
    sector: "FACILITY",
    sectorLabel: "Fuel Storage Ramp",
    sensorMode: "EO-OPTICAL",
    alt: "12m",
    telemetry: { lat: 32.7451, lon: 74.8789, heading: 45, status: "SURVEIL" },
    expectedTargets: ["truck", "fuel_bowser", "person"],
    description: "Outdoor petroleum and jet-fuel staging area with containment berms.",
    defaultDetections: [
      { label: "truck", confidence: 0.95, box: { x: 30, y: 34, w: 34, h: 40 } },
      { label: "person", confidence: 0.88, box: { x: 68, y: 44, w: 10, h: 28 } },
    ],
    dynamicTrajectories: [
      {
        id: "TRK-01",
        label: "truck",
        category: "vehicle",
        classification: "Aviation Fuel Bowser",
        baseConfidence: 0.95,
        speedKmh: 16,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 24, y: 28, w: 30, h: 36, confidence: 0.93 },
          { timePct: 0.5, x: 36, y: 40, w: 36, h: 44, confidence: 0.97 },
          { timePct: 1.0, x: 24, y: 28, w: 30, h: 36, confidence: 0.93 },
        ],
      },
      {
        id: "TRK-02",
        label: "person",
        category: "person",
        classification: "Fuel Quality Technician",
        baseConfidence: 0.89,
        speedKmh: 3,
        alertLevel: "normal",
        keyframes: [
          { timePct: 0.0, x: 64, y: 40, w: 9, h: 26, confidence: 0.87 },
          { timePct: 0.5, x: 72, y: 48, w: 11, h: 30, confidence: 0.91 },
          { timePct: 1.0, x: 64, y: 40, w: 9, h: 26, confidence: 0.87 },
        ],
      },
    ],
  },
];

export function getVideosBySector(sector: SurveillanceSectorId): SurveillanceVideo[] {
  if (sector === "ALL") return SURVEILLANCE_VIDEOS;
  return SURVEILLANCE_VIDEOS.filter((v) => v.sector === sector);
}
