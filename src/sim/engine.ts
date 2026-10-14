import { mulberry32, pick, between, type Rand } from "./prng";
import { getScenario } from "./scenarios";
import type {
  Depot,
  Person,
  SimEvent,
  SimSource,
  Severity,
  Unit,
  WeatherCell,
  Zone,
} from "./types";

export const BASE_LAT = 12.9716;
export const BASE_LON = 77.5946;

export const INDIAN_SECTORS: Record<
  string,
  {
    name: string;
    lat: number;
    lon: number;
    radius: number;
    weatherStationId: string;
    depotName: string;
    facilityType: "forward_operating_base" | "airbase" | "depot" | "naval_anchorage";
  }
> = {
  NORTH: {
    name: "Northern Sector (Ladakh High-Altitude)",
    lat: 34.1526,
    lon: 77.5771,
    radius: 0.35,
    weatherStationId: "STN-LEH",
    depotName: "NORTHERN FORWARD OPERATING BASE & DEPOT (LEH)",
    facilityType: "forward_operating_base",
  },
  KASHMIR: {
    name: "Northern Sector (Kashmir Valley)",
    lat: 34.0837,
    lon: 74.7973,
    radius: 0.3,
    weatherStationId: "STN-SRINAGAR",
    depotName: "KASHMIR VALLEY LOGISTICS & AIR SUPPORT HUB (SRINAGAR)",
    facilityType: "airbase",
  },
  NCR: {
    name: "Northern Sector (NCR / Plains)",
    lat: 28.6139,
    lon: 77.209,
    radius: 0.35,
    weatherStationId: "STN-DELHI",
    depotName: "NCR STRATEGIC LOGISTICS & RADAR FACILITY (DELHI)",
    facilityType: "depot",
  },
  WEST: {
    name: "Western Sector (Rajasthan / Thar)",
    lat: 26.9157,
    lon: 70.9083,
    radius: 0.4,
    weatherStationId: "STN-JAISALMER",
    depotName: "WESTERN DESERT TACTICAL LOGISTICS DEPOT (JAISALMER)",
    facilityType: "forward_operating_base",
  },
  KUTCH: {
    name: "Western Sector (Gujarat / Kutch Littoral)",
    lat: 23.242,
    lon: 69.6669,
    radius: 0.35,
    weatherStationId: "STN-BHUJ",
    depotName: "KUTCH LITTORAL & MARITIME SUPPORT DEPOT (BHUJ)",
    facilityType: "naval_anchorage",
  },
  CENTRAL: {
    name: "Central Sector (Nagpur Transit Corridor)",
    lat: 21.1458,
    lon: 79.0882,
    radius: 0.45,
    weatherStationId: "STN-NAGPUR",
    depotName: "CENTRAL LOGISTICS TRANSIT HUB (NAGPUR)",
    facilityType: "depot",
  },
  EAST: {
    name: "Eastern Sector (Odisha Coast / Paradip)",
    lat: 20.316,
    lon: 86.611,
    radius: 0.35,
    weatherStationId: "STN-PARADIP",
    depotName: "BAY OF BENGAL NAVAL & RESCUE DEPOT (PARADIP)",
    facilityType: "naval_anchorage",
  },
  BENGAL: {
    name: "Eastern Sector (West Bengal / Delta)",
    lat: 22.5726,
    lon: 88.3639,
    radius: 0.3,
    weatherStationId: "STN-KOLKATA",
    depotName: "EASTERN COMMAND AIR & LOGISTICS DEPOT (KOLKATA)",
    facilityType: "airbase",
  },
  NORTHEAST: {
    name: "North-Eastern Sector (Assam / Arunachal)",
    lat: 26.6338,
    lon: 92.7926,
    radius: 0.35,
    weatherStationId: "STN-TEZPUR",
    depotName: "BRAHMAPUTRA VALLEY FRONTIER AIRBASE DEPOT (TEZPUR)",
    facilityType: "airbase",
  },
  SOUTH: {
    name: "Southern Sector (Bengaluru Plateau)",
    lat: 12.9716,
    lon: 77.5946,
    radius: 0.3,
    weatherStationId: "STN-BENGALURU",
    depotName: "SOUTHERN COMMAND HEADQUARTERS DEPOT (BENGALURU)",
    facilityType: "depot",
  },
  LITTORAL: {
    name: "Littoral & Island Sector (Andaman & Nicobar)",
    lat: 11.6234,
    lon: 92.7265,
    radius: 0.25,
    weatherStationId: "STN-PORTBLAIR",
    depotName: "PORT BLAIR MARITIME SUPPORT DEPOT",
    facilityType: "naval_anchorage",
  },
};

export interface StrategicCorridor {
  id: string;
  name: string;
  fromSector: string;
  toSector: string;
  points: Array<[number, number]>;
  color: string;
  category: "highway" | "air" | "maritime";
}

export const STRATEGIC_SUPPLY_CORRIDORS: StrategicCorridor[] = [
  {
    id: "CORR-KASHMIR-LADAKH",
    name: "Northern Mountain Highway (Srinagar ↔ Leh)",
    fromSector: "KASHMIR",
    toSector: "NORTH",
    points: [
      [34.0837, 74.7973],
      [34.25, 75.35],
      [34.3, 76.15],
      [34.1526, 77.5771],
    ],
    color: "#38BDF8",
    category: "highway",
  },
  {
    id: "CORR-NCR-CENTRAL",
    name: "Grand Trunk Logistics Artery (Delhi ↔ Nagpur)",
    fromSector: "NCR",
    toSector: "CENTRAL",
    points: [
      [28.6139, 77.209],
      [26.45, 77.8],
      [23.85, 78.5],
      [21.1458, 79.0882],
    ],
    color: "#38BDF8",
    category: "highway",
  },
  {
    id: "CORR-WEST-DESERT",
    name: "Western Thar Border Corridor (Jaisalmer ↔ Bhuj)",
    fromSector: "WEST",
    toSector: "KUTCH",
    points: [
      [26.9157, 70.9083],
      [25.5, 70.8],
      [24.2, 70.2],
      [23.242, 69.6669],
    ],
    color: "#F59E0B",
    category: "highway",
  },
  {
    id: "CORR-CENTRAL-SOUTH",
    name: "Deccan Transit Spine (Nagpur ↔ Bengaluru)",
    fromSector: "CENTRAL",
    toSector: "SOUTH",
    points: [
      [21.1458, 79.0882],
      [18.5, 78.5],
      [15.5, 78.0],
      [12.9716, 77.5946],
    ],
    color: "#10B981",
    category: "highway",
  },
  {
    id: "CORR-EAST-COASTAL",
    name: "Bay of Bengal Coastal Route (Kolkata ↔ Paradip)",
    fromSector: "BENGAL",
    toSector: "EAST",
    points: [
      [22.5726, 88.3639],
      [21.8, 87.5],
      [21.0, 87.0],
      [20.316, 86.611],
    ],
    color: "#A855F7",
    category: "highway",
  },
  {
    id: "CORR-NORTHEAST-AXIS",
    name: "Brahmaputra Frontier Air-Ground Axis (Kolkata ↔ Tezpur)",
    fromSector: "BENGAL",
    toSector: "NORTHEAST",
    points: [
      [22.5726, 88.3639],
      [24.5, 89.8],
      [26.1, 91.5],
      [26.6338, 92.7926],
    ],
    color: "#06B6D4",
    category: "air",
  },
  {
    id: "CORR-LITTORAL-SEA",
    name: "Andaman Sea Sea Line of Communication (Paradip ↔ Port Blair)",
    fromSector: "EAST",
    toSector: "LITTORAL",
    points: [
      [20.316, 86.611],
      [17.5, 88.5],
      [14.5, 90.8],
      [11.6234, 92.7265],
    ],
    color: "#3B82F6",
    category: "maritime",
  },
  {
    id: "CORR-KUTCH-CENTRAL",
    name: "East-West Trans-Peninsular Link (Bhuj ↔ Nagpur)",
    fromSector: "KUTCH",
    toSector: "CENTRAL",
    points: [
      [23.242, 69.6669],
      [22.5, 72.8],
      [21.8, 76.2],
      [21.1458, 79.0882],
    ],
    color: "#EC4899",
    category: "highway",
  },
];

const PATROL_NAMES = ["ALPHA", "BRAVO", "CHARLIE", "DELTA", "ECHO", "FOXTROT", "GOLF", "HOTEL"];
const UAV_NAMES = ["RAVEN", "KITE", "FALCON", "OSPREY", "SHRIKE", "HARRIER", "MERLIN", "CONDOR"];
const CONVOY_NAMES = ["MULE", "CARAVAN", "IRONHORSE", "PACKHORSE", "OXCART", "DRAY"];
const SECTORS = ["A", "B", "C", "D"];
const FIRST = [
  "A. Rao",
  "S. Menon",
  "K. Iyer",
  "P. Singh",
  "N. Das",
  "R. Kapoor",
  "V. Nair",
  "M. Bose",
  "D. Sharma",
  "T. Chatterjee",
  "A. Kulkarni",
  "R. Varma",
];
const RANKS = ["SGT", "CPL", "LT", "PVT", "SSG", "CAPT"];

const INCIDENT_KINDS = [
  "unauthorized-entry",
  "signal-jamming",
  "vehicle-breakdown",
  "unidentified-contact",
  "perimeter-breach",
  "medical",
  "supply-shortfall",
];

const SEVERITIES: Severity[] = ["low", "medium", "high", "critical"];

function ring(rand: Rand, cx: number, cy: number, r: number, n: number): Array<[number, number]> {
  const pts: Array<[number, number]> = [];
  const phase = rand() * Math.PI * 2;
  for (let i = 0; i < n; i++) {
    const a = phase + (i / n) * Math.PI * 2;
    const rr = r * (0.7 + rand() * 0.6);
    pts.push([cx + Math.sin(a) * rr, cy + Math.cos(a) * rr]);
  }
  return pts;
}

export interface InitWorld {
  units: Unit[];
  depots: Depot[];
  personnel: Person[];
  zones: Zone[];
  weather?: WeatherCell[];
}

export function buildInitialWorld(seed: number, scenarioId: string): InitWorld {
  const rand = mulberry32(seed);
  const sc = getScenario(scenarioId);

  // Pan-India World Generation
  if (scenarioId.startsWith("IN-")) {
    const sectorKeys = Object.keys(INDIAN_SECTORS);
    const units: Unit[] = [];
    const personnel: Person[] = [];

    const mkIndia = (kind: Unit["kind"], callsign: string, i: number, secKey: string): Unit => {
      const sec = INDIAN_SECTORS[secKey]!;
      const cx = sec.lat + between(rand, -sec.radius * 0.5, sec.radius * 0.5);
      const cy = sec.lon + between(rand, -sec.radius * 0.5, sec.radius * 0.5);
      const route = ring(rand, cx, cy, sec.radius * (kind === "uav" ? 0.6 : 0.3), 6);
      return {
        id: `U-IN-${kind.toUpperCase()}-${i}`,
        callsign,
        kind,
        lat: route[0]![0],
        lon: route[0]![1],
        heading: 0,
        speedKph: kind === "uav" ? 120 : kind === "convoy" ? 48 : 8,
        status: "active",
        fuel: between(rand, 65, 100),
        battery: between(rand, 70, 100),
        lastSeenTick: 0,
        sector: secKey,
        route,
        personnelCount: kind === "uav" ? 1 : kind === "convoy" ? 2 : 3,
      };
    };

    // Tactical Patrols (2 per sector across all 11 sectors)
    for (let i = 0; i < sc.patrolCount; i++) {
      const secKey = sectorKeys[i % sectorKeys.length]!;
      const suffix = Math.floor(i / sectorKeys.length) === 0 ? "ALPHA" : "BRAVO";
      const u = mkIndia("patrol", `PATROL-${secKey}-${suffix}`, i + 1, secKey);
      units.push(u);
      const teamSize = 2 + Math.floor(rand() * 2);
      u.personnelCount = teamSize;
      const roles = ["Squad Leader", "Scout", "Combat Medic", "Comms Specialist"];
      for (let p = 0; p < teamSize; p++) {
        personnel.push({
          id: `P-${u.id}-${p}`,
          name: pick(rand, FIRST),
          rank: pick(rand, RANKS),
          unitId: u.id,
          heartRate: Math.round(between(rand, 65, 88)),
          fatigue: Number(between(rand, 0.05, 0.4).toFixed(2)),
          history: [],
          condition: "fit",
          role: roles[p % roles.length] || "Squad Leader",
          sector: secKey,
        });
      }
    }

    // UAV Surveillance Drones (1 per sector across all 11 sectors)
    for (let i = 0; i < sc.uavCount; i++) {
      const secKey = sectorKeys[i % sectorKeys.length]!;
      const u = mkIndia("uav", `UAV-${secKey}-${UAV_NAMES[i % UAV_NAMES.length]}`, i + 1, secKey);
      units.push(u);
      personnel.push({
        id: `P-${u.id}-0`,
        name: pick(rand, FIRST),
        rank: pick(rand, RANKS),
        unitId: u.id,
        heartRate: Math.round(between(rand, 68, 82)),
        fatigue: Number(between(rand, 0.05, 0.25).toFixed(2)),
        history: [],
        condition: "fit",
        role: "UAV Remote Pilot",
        sector: secKey,
      });
    }

    // Logistics Convoys (1 per sector across all 11 sectors)
    for (let i = 0; i < sc.convoyCount; i++) {
      const secKey = sectorKeys[i % sectorKeys.length]!;
      const u = mkIndia("convoy", `CONVOY-${secKey}-${CONVOY_NAMES[i % CONVOY_NAMES.length]}`, i + 1, secKey);
      units.push(u);
      const teamSize = 2;
      u.personnelCount = teamSize;
      for (let p = 0; p < teamSize; p++) {
        personnel.push({
          id: `P-${u.id}-${p}`,
          name: pick(rand, FIRST),
          rank: pick(rand, RANKS),
          unitId: u.id,
          heartRate: Math.round(between(rand, 70, 85)),
          fatigue: Number(between(rand, 0.1, 0.35).toFixed(2)),
          history: [],
          condition: "fit",
          role: p === 0 ? "Convoy Commander" : "Heavy Transport Driver",
          sector: secKey,
        });
      }
    }

    // Strategic Depots & Support Facilities across all 11 Indian sectors
    const depots: Depot[] = sectorKeys.map((secKey) => {
      const sec = INDIAN_SECTORS[secKey]!;
      return {
        id: `D-IN-${secKey}`,
        name: sec.depotName,
        lat: sec.lat,
        lon: sec.lon,
        stock: {
          fuel: Math.round(between(rand, 3800, 6500)),
          medkit: Math.round(between(rand, 100, 250)),
          rations: Math.round(between(rand, 600, 1500)),
          battery: Math.round(between(rand, 120, 350)),
        },
        capacity: { fuel: 8000, medkit: 350, rations: 2000, battery: 500 },
        sector: secKey,
        facilityType: sec.facilityType,
      };
    });

    // Strategic Tactical Zones covering all 11 Indian sectors
    const zones: Zone[] = sectorKeys.map((secKey) => {
      const sec = INDIAN_SECTORS[secKey]!;
      const kind: Zone["kind"] =
        secKey === "EAST"
          ? "threat"
          : secKey === "WEST" || secKey === "KUTCH" || secKey === "LITTORAL"
            ? "restricted"
            : "patrol";
      return {
        id: `Z-IN-${secKey}`,
        name: `${sec.name.toUpperCase()} TACTICAL GRID`,
        kind,
        points: ring(rand, sec.lat, sec.lon, sec.radius * 1.1, 7),
        sector: secKey,
      };
    });

    const weather: WeatherCell[] = [];
    if (scenarioId === "IN-SC-CYCLONE") {
      weather.push({
        id: "W-CYCLONE-BOB",
        lat: 18.5,
        lon: 87.2,
        radiusM: 180000,
        intensity: 0.95,
        kind: "storm",
      });
    } else if (scenarioId === "IN-SC-NORTH-COMMS") {
      weather.push({
        id: "W-BLIZZARD-LEH",
        lat: 34.15,
        lon: 77.58,
        radiusM: 95000,
        intensity: 0.9,
        kind: "storm",
      });
    } else if (scenarioId === "IN-SC-WEST-HEAT") {
      weather.push({
        id: "W-HEATWAVE-THAR",
        lat: 26.91,
        lon: 70.91,
        radiusM: 120000,
        intensity: 0.92,
        kind: "dust",
      });
    } else if (scenarioId === "IN-SC-CASCADE") {
      weather.push(
        {
          id: "W-CYCLONE-BOB",
          lat: 18.5,
          lon: 87.2,
          radiusM: 180000,
          intensity: 0.95,
          kind: "storm",
        },
        {
          id: "W-BLIZZARD-LEH",
          lat: 34.15,
          lon: 77.58,
          radiusM: 95000,
          intensity: 0.9,
          kind: "storm",
        },
        {
          id: "W-HEATWAVE-THAR",
          lat: 26.91,
          lon: 70.91,
          radiusM: 120000,
          intensity: 0.92,
          kind: "dust",
        },
        {
          id: "W-SQUALL-ANDAMAN",
          lat: 11.62,
          lon: 92.73,
          radiusM: 80000,
          intensity: 0.85,
          kind: "rain",
        },
      );
    }

    return { units, depots, personnel, zones, weather };
  }

  // Legacy SC-1..SC-4 World Generation
  const units: Unit[] = [];
  const personnel: Person[] = [];

  const mk = (kind: Unit["kind"], callsign: string, i: number): Unit => {
    const cx = BASE_LAT + between(rand, -0.05, 0.05);
    const cy = BASE_LON + between(rand, -0.05, 0.05);
    const route = ring(rand, cx, cy, kind === "uav" ? 0.03 : 0.018, 6);
    return {
      id: `U-${kind.toUpperCase()}-${i}`,
      callsign,
      kind,
      lat: route[0]![0],
      lon: route[0]![1],
      heading: 0,
      speedKph: kind === "uav" ? 68 : kind === "convoy" ? 34 : 6,
      status: "active",
      fuel: between(rand, 55, 100),
      battery: between(rand, 60, 100),
      lastSeenTick: 0,
      sector: pick(rand, SECTORS),
      route,
    };
  };

  for (let i = 0; i < sc.patrolCount; i++) {
    const u = mk("patrol", `${PATROL_NAMES[i % PATROL_NAMES.length]}-${1 + (i % 3)}`, i + 1);
    units.push(u);
    const teamSize = 2 + Math.floor(rand() * 2);
    for (let p = 0; p < teamSize; p++) {
      personnel.push({
        id: `P-${u.id}-${p}`,
        name: pick(rand, FIRST),
        rank: pick(rand, RANKS),
        unitId: u.id,
        heartRate: Math.round(between(rand, 62, 92)),
        fatigue: Number(between(rand, 0.1, 0.55).toFixed(2)),
        history: [],
      });
    }
  }
  for (let i = 0; i < sc.uavCount; i++)
    units.push(mk("uav", `${UAV_NAMES[i % UAV_NAMES.length]}-${1 + (i % 3)}`, i + 1));
  for (let i = 0; i < sc.convoyCount; i++)
    units.push(mk("convoy", `${CONVOY_NAMES[i % CONVOY_NAMES.length]}-${1 + (i % 3)}`, i + 1));

  const depots: Depot[] = ["NORTH", "CENTRAL", "SOUTH"].map((n, i) => ({
    id: `D-${i + 1}`,
    name: `${n} DEPOT`,
    lat: BASE_LAT + between(rand, -0.04, 0.04),
    lon: BASE_LON + between(rand, -0.04, 0.04),
    stock: {
      fuel: Math.round(between(rand, 2200, 4000)),
      medkit: Math.round(between(rand, 60, 140)),
      rations: Math.round(between(rand, 300, 700)),
      battery: Math.round(between(rand, 80, 200)),
    },
    capacity: { fuel: 4000, medkit: 150, rations: 700, battery: 200 },
  }));

  const zones: Zone[] = [
    {
      id: "Z-1",
      name: "PATROL GRID NORTH",
      kind: "patrol",
      points: ring(rand, BASE_LAT + 0.03, BASE_LON - 0.02, 0.035, 7),
    },
    {
      id: "Z-2",
      name: "PATROL GRID SOUTH",
      kind: "patrol",
      points: ring(rand, BASE_LAT - 0.035, BASE_LON + 0.02, 0.03, 6),
    },
    {
      id: "Z-3",
      name: "RESTRICTED AIRSPACE R-12",
      kind: "restricted",
      points: ring(rand, BASE_LAT + 0.01, BASE_LON + 0.045, 0.022, 5),
    },
    {
      id: "Z-4",
      name: "THREAT SECTOR C",
      kind: "threat",
      points: ring(rand, BASE_LAT - 0.02, BASE_LON - 0.045, 0.026, 6),
    },
  ];

  return { units, depots, personnel, zones };
}

export class MockSimSource implements SimSource {
  private rand: Rand = mulberry32(1);
  private timer: ReturnType<typeof setInterval> | null = null;
  private listeners = new Set<(e: SimEvent[]) => void>();
  private nextId = 1;
  private tick = 0;
  private speed = 1;
  private seed = 20260101;
  private scenarioId = "SC-1";
  private units: Unit[] = [];
  private weather: WeatherCell[] = [];
  private personnel: Person[] = [];
  private depots: Depot[] = [];
  private routeIdx = new Map<string, number>();
  private silence = new Map<string, number>();

  private emit(partials: Array<Pick<SimEvent, "type" | "severity" | "entityId" | "payload">>) {
    if (!partials.length) return;
    const events: SimEvent[] = partials.map((p) => ({
      id: this.nextId++,
      tick: this.tick,
      simTime: this.tick * 1000,
      ...p,
    }));
    this.listeners.forEach((l) => l(events));
  }

  subscribe(cb: (events: SimEvent[]) => void) {
    this.listeners.add(cb);
    return () => this.listeners.delete(cb);
  }

  start({ seed, scenarioId }: { seed: number; scenarioId: string }) {
    this.stopTimer();
    this.seed = seed;
    this.scenarioId = scenarioId;
    this.rand = mulberry32(seed);
    this.nextId = 1;
    this.tick = 0;
    this.routeIdx.clear();
    this.silence.clear();
    const world = buildInitialWorld(seed, scenarioId);
    this.units = world.units.map((u) => ({ ...u }));
    this.personnel = world.personnel.map((p) => ({ ...p }));
    this.depots = world.depots.map((d) => ({ ...d, stock: { ...d.stock } }));
    this.weather = world.weather ? world.weather.map((w) => ({ ...w })) : [];
    this.emit([
      {
        type: "world_init",
        severity: "low",
        entityId: "system",
        payload: {
          seed,
          scenarioId,
          worldMode: scenarioId === "IN-BASE-LIVE" ? "baseline" : "simulation",
          ...world,
        },
      },
    ]);
    this.startTimer();
  }

  pause() {
    this.stopTimer();
    this.emit([
      { type: "system", severity: "low", entityId: "system", payload: { status: "PAUSED" } },
    ]);
  }

  resume() {
    if (this.timer) return;
    this.emit([
      { type: "system", severity: "low", entityId: "system", payload: { status: "RUNNING" } },
    ]);
    this.startTimer();
  }

  stop() {
    this.stopTimer();
    this.emit([
      { type: "system", severity: "low", entityId: "system", payload: { status: "STOPPED" } },
    ]);
  }

  setSpeed(speed: number) {
    this.speed = speed;
    this.emit([{ type: "system", severity: "low", entityId: "system", payload: { speed } }]);
    if (this.timer) {
      this.stopTimer();
      this.startTimer();
    }
  }

  inject(events: Omit<SimEvent, "id" | "tick" | "simTime">[]) {
    for (const e of events) {
      const p = e.payload as { mission?: boolean; route?: Array<[number, number]> };
      if (e.type === "system" && p.mission && p.route?.length) {
        const unit = this.units.find((u) => u.id === e.entityId);
        if (unit) {
          unit.route = p.route;
          this.routeIdx.set(unit.id, 0);
        }
      }
    }
    this.emit(events);
  }

  isRunning() {
    return this.timer !== null;
  }

  private startTimer() {
    const clampedSpeed = Math.max(1, Math.min(20, this.speed));
    this.timer = setInterval(() => this.step(), Math.max(25, 1000 / clampedSpeed));
  }

  private stopTimer() {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
  }

  step() {
    if (this.scenarioId.startsWith("IN-")) {
      return this.stepPanIndia();
    }

    // Legacy SC-1..SC-4 Step
    this.tick += 1;
    const rand = this.rand;
    const sc = getScenario(this.scenarioId);
    const out: Array<Pick<SimEvent, "type" | "severity" | "entityId" | "payload">> = [];

    // weather cells drift / spawn / clear
    if (rand() < sc.weatherRate && this.weather.length < 4) {
      const cell: WeatherCell = {
        id: `W-${this.tick}`,
        lat: BASE_LAT + between(rand, -0.05, 0.05),
        lon: BASE_LON + between(rand, -0.05, 0.05),
        radiusM: Math.round(between(rand, 900, 2600)),
        intensity: Number(between(rand, 0.3, 1).toFixed(2)),
        kind: pick(rand, ["rain", "storm", "fog", "dust"]),
      };
      this.weather.push(cell);
      out.push({
        type: "weather_spawn",
        severity: cell.intensity > 0.7 ? "high" : "medium",
        entityId: cell.id,
        payload: { ...cell },
      });
    }
    this.weather = this.weather.filter((w) => {
      w.lat += between(rand, -0.0016, 0.0016);
      w.lon += between(rand, -0.0016, 0.0016);
      w.intensity = Number(Math.max(0, w.intensity - 0.004).toFixed(3));
      if (w.intensity <= 0.05) {
        out.push({ type: "weather_clear", severity: "low", entityId: w.id, payload: {} });
        return false;
      }
      out.push({
        type: "weather_move",
        severity: "low",
        entityId: w.id,
        payload: { lat: w.lat, lon: w.lon, intensity: w.intensity },
      });
      return true;
    });

    for (const u of this.units) {
      const silentUntil = this.silence.get(u.id) ?? 0;
      if (silentUntil > this.tick) continue;
      if (rand() < 0.004) {
        this.silence.set(u.id, this.tick + Math.round(between(rand, 180, 320)));
        out.push({
          type: "comms_loss",
          severity: "high",
          entityId: u.id,
          payload: { callsign: u.callsign },
        });
        out.push({
          type: "alert_raise",
          severity: "high",
          entityId: u.id,
          payload: {
            message: `${u.callsign} comms silence detected`,
            alertId: `AL-${this.tick}-${u.id}`,
          },
        });
        continue;
      }
      if (silentUntil === this.tick) {
        out.push({
          type: "comms_restore",
          severity: "low",
          entityId: u.id,
          payload: { callsign: u.callsign },
        });
      }

      const idx = this.routeIdx.get(u.id) ?? 0;
      const target = u.route[idx % u.route.length]!;
      const dLat = target[0] - u.lat;
      const dLon = target[1] - u.lon;
      const dist = Math.hypot(dLat, dLon);
      const inWeather = this.weather.some(
        (w) => Math.hypot(w.lat - u.lat, w.lon - u.lon) * 111000 < w.radiusM,
      );
      const base = (u.speedKph / 3600 / 111) * (inWeather ? 0.45 : 1) * 4;
      if (dist < base * 1.2) {
        this.routeIdx.set(u.id, idx + 1);
      } else {
        u.lat += (dLat / dist) * base;
        u.lon += (dLon / dist) * base;
        u.heading = (Math.atan2(dLon, dLat) * 180) / Math.PI;
      }
      const status = inWeather ? "slowed" : "active";
      if (status !== u.status) {
        u.status = status;
        out.push({ type: "unit_status", severity: "low", entityId: u.id, payload: { status } });
      }
      u.lastSeenTick = this.tick;
      out.push({
        type: "unit_move",
        severity: "low",
        entityId: u.id,
        payload: { lat: u.lat, lon: u.lon, heading: u.heading, inWeather },
      });

      // resources
      if (this.tick % 5 === 0) {
        u.fuel = Math.max(0, u.fuel - between(rand, 0.05, 0.35));
        u.battery = Math.max(0, u.battery - between(rand, 0.1, 0.5) * (u.kind === "uav" ? 2 : 1));
        out.push({
          type: "resource_level",
          severity: u.battery < 15 || u.fuel < 15 ? "high" : "low",
          entityId: u.id,
          payload: { fuel: Number(u.fuel.toFixed(1)), battery: Number(u.battery.toFixed(1)) },
        });
        if (u.battery < 12) {
          out.push({
            type: "alert_raise",
            severity: "critical",
            entityId: u.id,
            payload: {
              message: `${u.callsign} battery critical (${u.battery.toFixed(0)}%)`,
              alertId: `AL-${this.tick}-BAT-${u.id}`,
            },
          });
        }
      }

      // detections from UAVs
      if (u.kind === "uav" && rand() < 0.02) {
        out.push({
          type: "detection",
          severity: "medium",
          entityId: u.id,
          payload: {
            label: pick(rand, ["vehicle", "person", "uav", "structure"]),
            confidence: Number(between(rand, 0.45, 0.98).toFixed(2)),
            model: "yolov8n-doip-v1.4",
            lat: u.lat,
            lon: u.lon,
            frame: `F-${this.tick}-${u.id}`,
          },
        });
      }
    }

    // depot burn
    if (this.tick % 10 === 0) {
      for (const d of this.depots) {
        d.stock.fuel = Math.max(0, d.stock.fuel - Math.round(between(rand, 2, 14)));
        d.stock.medkit = Math.max(0, d.stock.medkit - (rand() < 0.3 ? 1 : 0));
        d.stock.rations = Math.max(0, d.stock.rations - Math.round(between(rand, 1, 5)));
        d.stock.battery = Math.max(0, d.stock.battery - (rand() < 0.5 ? 1 : 0));
        out.push({
          type: "resource_level",
          severity: d.stock.fuel < 600 ? "high" : "low",
          entityId: d.id,
          payload: { stock: { ...d.stock } },
        });
      }
    }

    // vitals
    if (this.tick % 8 === 0) {
      for (const p of this.personnel) {
        p.heartRate = Math.round(Math.min(180, Math.max(52, p.heartRate + between(rand, -5, 6))));
        p.fatigue = Number(Math.min(1, p.fatigue + between(rand, -0.004, 0.012)).toFixed(3));
        out.push({
          type: "vitals",
          severity: p.fatigue > 0.8 ? "high" : "low",
          entityId: p.id,
          payload: { heartRate: p.heartRate, fatigue: p.fatigue },
        });
      }
    }

    // incidents
    if (rand() < sc.incidentRate) {
      const u = pick(rand, this.units);
      const sev =
        SEVERITIES[Math.min(3, Math.floor(rand() * 4 + (sc.incidentRate > 0.1 ? 0.6 : 0)))]!;
      const id = `INC-${this.tick}`;
      out.push({
        type: "incident_open",
        severity: sev,
        entityId: id,
        payload: {
          kind: pick(rand, INCIDENT_KINDS),
          lat: u.lat + between(rand, -0.004, 0.004),
          lon: u.lon + between(rand, -0.004, 0.004),
          reportedBy: u.id,
          callsign: u.callsign,
        },
      });
      out.push({
        type: "alert_raise",
        severity: sev,
        entityId: id,
        payload: { message: `Incident ${id} reported by ${u.callsign}`, alertId: `AL-${id}` },
      });
    }

    this.emit(out);
  }

  private stepPanIndia() {
    this.tick += 1;
    const rand = this.rand;
    const sc = getScenario(this.scenarioId);
    const scId = this.scenarioId;
    const out: Array<Pick<SimEvent, "type" | "severity" | "entityId" | "payload">> = [];

    // Weather updates
    for (const w of this.weather) {
      if (w.id.includes("CYCLONE")) {
        w.lat += between(rand, 0.003, 0.008);
        w.lon -= between(rand, 0.002, 0.006);
        out.push({
          type: "weather_move",
          severity: "high",
          entityId: w.id,
          payload: {
            lat: Number(w.lat.toFixed(4)),
            lon: Number(w.lon.toFixed(4)),
            intensity: w.intensity,
            name: "Cyclone Vardah-Sim",
          },
        });
      } else if (w.id.includes("BLIZZARD")) {
        w.lat += between(rand, -0.002, 0.002);
        w.lon += between(rand, -0.002, 0.002);
        out.push({
          type: "weather_move",
          severity: "high",
          entityId: w.id,
          payload: {
            lat: Number(w.lat.toFixed(4)),
            lon: Number(w.lon.toFixed(4)),
            intensity: w.intensity,
            name: "Himalayan Blizzard Cell",
          },
        });
      } else if (w.id.includes("HEATWAVE")) {
        w.lat += between(rand, -0.001, 0.001);
        w.lon += between(rand, -0.001, 0.001);
        out.push({
          type: "weather_move",
          severity: "medium",
          entityId: w.id,
          payload: {
            lat: Number(w.lat.toFixed(4)),
            lon: Number(w.lon.toFixed(4)),
            intensity: w.intensity,
            name: "Thar High Thermal Cell",
          },
        });
      } else if (w.id.includes("SQUALL")) {
        w.lat += between(rand, -0.003, 0.003);
        w.lon += between(rand, -0.003, 0.003);
        out.push({
          type: "weather_move",
          severity: "medium",
          entityId: w.id,
          payload: {
            lat: Number(w.lat.toFixed(4)),
            lon: Number(w.lon.toFixed(4)),
            intensity: w.intensity,
            name: "Andaman Maritime Squall",
          },
        });
      } else {
        w.lat += between(rand, -0.001, 0.001);
        w.lon += between(rand, -0.001, 0.001);
        out.push({
          type: "weather_move",
          severity: "low",
          entityId: w.id,
          payload: { lat: Number(w.lat.toFixed(4)), lon: Number(w.lon.toFixed(4)), intensity: w.intensity },
        });
      }
    }

    for (const u of this.units) {
      const silentUntil = this.silence.get(u.id) ?? 0;
      if (silentUntil > this.tick) continue;

      const commsFailRate =
        (scId === "IN-SC-NORTH-COMMS" || scId === "IN-SC-CASCADE") && u.sector === "NORTH"
          ? 0.025
          : 0.004;
      if (rand() < commsFailRate) {
        this.silence.set(u.id, this.tick + Math.round(between(rand, 180, 420)));
        out.push({
          type: "comms_loss",
          severity: "high",
          entityId: u.id,
          payload: { callsign: u.callsign, sector: u.sector },
        });
        out.push({
          type: "alert_raise",
          severity: "high",
          entityId: u.id,
          payload: {
            message: `${u.callsign} RF link silence in ${u.sector} sector`,
            alertId: `AL-IN-${this.tick}-${u.id}`,
          },
        });
        continue;
      }
      if (silentUntil === this.tick) {
        out.push({
          type: "comms_restore",
          severity: "low",
          entityId: u.id,
          payload: { callsign: u.callsign },
        });
      }

      const idx = this.routeIdx.get(u.id) ?? 0;
      const target = u.route[idx % u.route.length]!;
      const dLat = target[0] - u.lat;
      const dLon = target[1] - u.lon;
      const dist = Math.hypot(dLat, dLon);
      const inWeather = this.weather.some(
        (w) => Math.hypot(w.lat - u.lat, w.lon - u.lon) * 111000 < w.radiusM,
      );

      let speedMult = 1.0;
      if (inWeather) {
        speedMult = scId === "IN-SC-CYCLONE" || scId === "IN-SC-CASCADE" ? 0.35 : 0.5;
      }
      if (
        (scId === "IN-SC-LOGISTICS" || scId === "IN-SC-CASCADE") &&
        u.sector === "CENTRAL" &&
        u.kind === "convoy"
      ) {
        speedMult = 0.15;
      }

      const base = (u.speedKph / 3600 / 111) * speedMult * 4;
      if (dist < base * 1.2) {
        this.routeIdx.set(u.id, idx + 1);
      } else {
        u.lat += (dLat / dist) * base;
        u.lon += (dLon / dist) * base;
        u.heading = (Math.atan2(dLon, dLat) * 180) / Math.PI;
      }

      const status = speedMult <= 0.2 ? "halted" : speedMult < 0.7 ? "slowed" : "active";
      if (status !== u.status) {
        u.status = status;
        out.push({
          type: "unit_status",
          severity: status === "halted" ? "medium" : "low",
          entityId: u.id,
          payload: { status },
        });
      }
      u.lastSeenTick = this.tick;
      out.push({
        type: "unit_move",
        severity: "low",
        entityId: u.id,
        payload: {
          lat: Number(u.lat.toFixed(5)),
          lon: Number(u.lon.toFixed(5)),
          heading: Number(u.heading.toFixed(1)),
          inWeather,
          sector: u.sector,
        },
      });

      if (this.tick % 5 === 0) {
        const fuelRateMult =
          (scId === "IN-SC-WEST-HEAT" || scId === "IN-SC-CASCADE") && u.sector === "WEST"
            ? 2.4
            : 1.0;
        u.fuel = Math.max(0, u.fuel - between(rand, 0.05, 0.35) * fuelRateMult);
        const batRateMult =
          (scId === "IN-SC-NORTH-COMMS" || scId === "IN-SC-CASCADE") && u.sector === "NORTH"
            ? 3.0
            : 1.0;
        u.battery = Math.max(
          0,
          u.battery - between(rand, 0.1, 0.5) * (u.kind === "uav" ? 2 : 1) * batRateMult,
        );

        out.push({
          type: "resource_level",
          severity: u.battery < 15 || u.fuel < 15 ? "high" : "low",
          entityId: u.id,
          payload: { fuel: Number(u.fuel.toFixed(1)), battery: Number(u.battery.toFixed(1)) },
        });
        if (u.battery < 12) {
          out.push({
            type: "alert_raise",
            severity: "critical",
            entityId: u.id,
            payload: {
              message: `${u.callsign} battery critical (${u.battery.toFixed(0)}%)`,
              alertId: `AL-IN-${this.tick}-BAT-${u.id}`,
            },
          });
        }
      }

      if (u.kind === "uav" && rand() < 0.025) {
        out.push({
          type: "detection",
          severity: "medium",
          entityId: u.id,
          payload: {
            label: pick(rand, ["patrol", "transport", "relay-station", "radar-contact"]),
            confidence: Number(between(rand, 0.55, 0.98).toFixed(2)),
            model: "yolov8n-pan-india-v2.0",
            lat: Number(u.lat.toFixed(5)),
            lon: Number(u.lon.toFixed(5)),
            sector: u.sector,
            frame: `F-IN-${this.tick}-${u.id}`,
          },
        });
      }
    }

    if (this.tick % 10 === 0) {
      for (const d of this.depots) {
        const burnMult =
          (scId === "IN-SC-LOGISTICS" || scId === "IN-SC-CASCADE") && d.id === "D-IN-CENTRAL"
            ? 3.5
            : 1.0;
        d.stock.fuel = Math.max(0, d.stock.fuel - Math.round(between(rand, 3, 20) * burnMult));
        d.stock.rations = Math.max(0, d.stock.rations - Math.round(between(rand, 2, 8) * burnMult));
        d.stock.medkit = Math.max(0, d.stock.medkit - (rand() < 0.25 ? 1 : 0));
        d.stock.battery = Math.max(0, d.stock.battery - (rand() < 0.4 ? 1 : 0));
        const isCrit = d.stock.fuel < 1000 || d.stock.rations < 200;
        out.push({
          type: "resource_level",
          severity: isCrit ? "critical" : "low",
          entityId: d.id,
          payload: { stock: { ...d.stock } },
        });
        if (isCrit && this.tick % 30 === 0) {
          out.push({
            type: "alert_raise",
            severity: "critical",
            entityId: d.id,
            payload: {
              message: `Supply depletion alert at ${d.name}`,
              alertId: `AL-IN-DEP-${this.tick}-${d.id}`,
            },
          });
        }
      }
    }

    if (rand() < sc.incidentRate) {
      const u = pick(rand, this.units);
      let incKind = pick(rand, INCIDENT_KINDS);
      if (scId === "IN-SC-LOGISTICS") incKind = "supply-shortfall";
      else if (scId === "IN-SC-NORTH-COMMS") incKind = "signal-jamming";
      else if (scId === "IN-SC-WEST-HEAT") incKind = "vehicle-breakdown";
      else if (scId === "IN-SC-CASCADE") {
        if (u.sector === "NORTH") incKind = "signal-jamming";
        else if (u.sector === "WEST") incKind = "vehicle-breakdown";
        else if (u.sector === "CENTRAL") incKind = "supply-shortfall";
        else if (u.sector === "EAST") incKind = "perimeter-breach";
        else incKind = pick(rand, INCIDENT_KINDS);
      }

      const incId = `INC-IN-${this.tick}`;
      const sev: Severity =
        incKind === "supply-shortfall" || incKind === "signal-jamming" ? "critical" : "high";
      out.push({
        type: "incident_open",
        severity: sev,
        entityId: incId,
        payload: {
          kind: incKind,
          lat: Number((u.lat + between(rand, -0.01, 0.01)).toFixed(5)),
          lon: Number((u.lon + between(rand, -0.01, 0.01)).toFixed(5)),
          sector: u.sector,
          reportedBy: u.id,
          callsign: u.callsign,
        },
      });
      out.push({
        type: "alert_raise",
        severity: sev,
        entityId: incId,
        payload: {
          message: `Incident ${incId} (${incKind}) reported in ${u.sector} by ${u.callsign}`,
          alertId: `AL-${incId}`,
        },
      });
    }

    this.emit(out);
  }
}

export const simSource = new MockSimSource();
