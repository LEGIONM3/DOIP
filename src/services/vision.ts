/**
 * Vision Analytics & Tracking Service (Phase 3B)
 * Connects frontend to object detection, multi-frame tracking, and perimeter intrusion API.
 */

export interface VisionDetectionItem {
  id: string;
  frame_id?: string;
  tick: number;
  entity_id: string;
  class_label: string;
  confidence: number;
  box_x?: number;
  box_y?: number;
  box_w?: number;
  box_h?: number;
  lat?: number;
  lon?: number;
  metadata?: Record<string, any>;
  created_at?: string;
}

export interface VisionTrackItem {
  id?: number;
  track_id: string;
  class_label: string;
  frame_id?: string;
  tick: number;
  lat?: number;
  lon?: number;
  velocity_mps: number;
  heading_deg: number;
  activity_state: 'nominal' | 'in_transit' | 'stalled' | 'intruding' | 'suspicious' | string;
  history?: Array<{
    tick: number;
    lat: number;
    lon: number;
    velocity_mps: number;
    heading_deg: number;
    activity_state: string;
  }>;
  metadata?: Record<string, any>;
  updated_at?: string;
}

export interface VisionIntrusion {
  track_id?: string;
  zone_id: string;
  zone_name: string;
  zone_type: string;
  lat: number;
  lon: number;
  tick: number;
  severity: 'WARNING' | 'CRITICAL';
}

export interface AdjudicationResponse {
  detections: VisionDetectionItem[];
  tracks: VisionTrackItem[];
  intrusions: VisionIntrusion[];
  analytics: {
    tracks_count: number;
    intrusions_count: number;
    activity_states: Record<string, number>;
  };
}

const API_BASE = '';

export async function fetchVisionTracks(limit: number = 50): Promise<VisionTrackItem[]> {
  const resp = await fetch(`${API_BASE}/vision/tracks?limit=${limit}`);
  if (!resp.ok) {
    throw new Error(`Fetch vision tracks failed: ${resp.status}`);
  }
  return resp.json();
}

export async function fetchVisionDetections(limit: number = 50): Promise<VisionDetectionItem[]> {
  const resp = await fetch(`${API_BASE}/vision/detections?limit=${limit}`);
  if (!resp.ok) {
    throw new Error(`Fetch vision detections failed: ${resp.status}`);
  }
  return resp.json();
}

export async function adjudicateVisionFrame(
  frameId: string,
  tick: number,
  detections: any[] = []
): Promise<AdjudicationResponse> {
  const resp = await fetch(`${API_BASE}/vision/adjudicate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      frame_id: frameId,
      tick,
      detections,
    }),
  });
  if (!resp.ok) {
    throw new Error(`Vision adjudication failed: ${resp.status}`);
  }
  return resp.json();
}
