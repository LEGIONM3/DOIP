export interface Scenario {
  id: string;
  name: string;
  description: string;
  incidentRate: number;
  weatherRate: number;
  uavCount: number;
  patrolCount: number;
  convoyCount: number;
  validation: "valid" | "warning";
  category?: "legacy" | "live-baseline" | "artificial-impact";
  sector?: string;
}

export const SCENARIOS: Scenario[] = [
  {
    id: "SC-1",
    name: "Night Patrol Baseline",
    description: "Routine night patrol grid over the northern sectors. Low threat baseline.",
    incidentRate: 0.05,
    weatherRate: 0.02,
    uavCount: 4,
    patrolCount: 8,
    convoyCount: 3,
    validation: "valid",
    category: "legacy",
    sector: "Bengaluru Local",
  },
  {
    id: "SC-2",
    name: "Border Surveillance",
    description: "Extended perimeter watch with elevated sensor tasking and comms strain.",
    incidentRate: 0.09,
    weatherRate: 0.04,
    uavCount: 6,
    patrolCount: 7,
    convoyCount: 2,
    validation: "valid",
    category: "legacy",
    sector: "Bengaluru Local",
  },
  {
    id: "SC-3",
    name: "Counter-UAV Airspace Watch",
    description: "Dense hostile-UAV activity, high detection load, frequent critical alerts.",
    incidentRate: 0.14,
    weatherRate: 0.03,
    uavCount: 8,
    patrolCount: 5,
    convoyCount: 2,
    validation: "valid",
    category: "legacy",
    sector: "Bengaluru Local",
  },
  {
    id: "SC-4",
    name: "Convoy Escort",
    description: "Logistics convoy movement under escort with weather interference.",
    incidentRate: 0.1,
    weatherRate: 0.08,
    uavCount: 3,
    patrolCount: 6,
    convoyCount: 6,
    validation: "warning",
    category: "legacy",
    sector: "Bengaluru Local",
  },
  // --- Pan-India Live Context Baseline & Artificial Impact Scenarios ---
  {
    id: "IN-BASE-LIVE",
    name: "Pan-India Live Context Baseline",
    description: "Live Indian meteorological context baseline with distributed synthetic operational entities.",
    incidentRate: 0.04,
    weatherRate: 0.02,
    uavCount: 8,
    patrolCount: 12,
    convoyCount: 6,
    validation: "valid",
    category: "live-baseline",
    sector: "Pan-India",
  },
  {
    id: "IN-SC-CYCLONE",
    name: "Bay of Bengal Severe Cyclone & Coastal Flooding",
    description: "Category 3 cyclone landfall along Odisha-AP coastal corridor with high winds, storm surges, and port supply chokepoints.",
    incidentRate: 0.16,
    weatherRate: 0.15,
    uavCount: 6,
    patrolCount: 8,
    convoyCount: 4,
    validation: "valid",
    category: "artificial-impact",
    sector: "Eastern Littoral",
  },
  {
    id: "IN-SC-NORTH-COMMS",
    name: "Himalayan High-Altitude Comms Blackout & Blizzard",
    description: "Severe mountain blizzard and total RF communication blackout across the Northern Ladakh frontier.",
    incidentRate: 0.12,
    weatherRate: 0.1,
    uavCount: 6,
    patrolCount: 10,
    convoyCount: 4,
    validation: "valid",
    category: "artificial-impact",
    sector: "Northern Frontier",
  },
  {
    id: "IN-SC-WEST-HEAT",
    name: "Thar Desert Extreme Heatwave & Fuel Boil-off",
    description: "48°C extreme thermal conditions in the Western Desert causing accelerated fuel evaporation, sensor degradation, and engine halts.",
    incidentRate: 0.11,
    weatherRate: 0.05,
    uavCount: 7,
    patrolCount: 8,
    convoyCount: 5,
    validation: "valid",
    category: "artificial-impact",
    sector: "Western Desert",
  },
  {
    id: "IN-SC-LOGISTICS",
    name: "Central Corridor Supply Chokepoint & Depot Breakdown",
    description: "Railway and transit hub logistics failure at Central transit corridor (Nagpur) with rapid forward supply exhaustion.",
    incidentRate: 0.14,
    weatherRate: 0.03,
    uavCount: 5,
    patrolCount: 8,
    convoyCount: 8,
    validation: "warning",
    category: "artificial-impact",
    sector: "Central Corridor",
  },
  {
    id: "IN-SC-CASCADE",
    name: "Pan-India Multi-Sector Cascading Crisis",
    description: "Simultaneous compound crisis across all Indian sectors: Eastern cyclone, Northern blizzard & comms blackout, Western desert fuel boil-off, and Central corridor freight failure.",
    incidentRate: 0.18,
    weatherRate: 0.16,
    uavCount: 10,
    patrolCount: 14,
    convoyCount: 8,
    validation: "warning",
    category: "artificial-impact",
    sector: "All-India Subcontinent",
  },
];

export const getScenario = (id: string) => SCENARIOS.find((s) => s.id === id) ?? SCENARIOS[0]!;
