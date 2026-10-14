/**
 * Enterprise Event Streaming & Operational Data Lake Service (Phases 4I, 4J)
 */

export interface StreamEvent {
  id?: number;
  stream_name: string;
  offset: number;
  partition: number;
  event_type: string;
  payload: Record<string, any>;
  timestamp: string;
}

export interface StreamProjection {
  stream_name: string;
  total_events_in_buffer: number;
  latest_offset: number;
  event_types_breakdown: Record<string, number>;
  last_event: StreamEvent | null;
  timestamp: string;
}

export interface DataLakeObject {
  id: string;
  bucket: string;
  key: string;
  content_type: string;
  size_bytes: number;
  etag: string;
  metadata?: Record<string, any>;
  created_at: string;
  data?: any;
}

export interface DataLakeAnalysis {
  total_objects: number;
  total_size_bytes: number;
  total_size_kb: number;
  buckets_distribution: Record<string, number>;
  object_types: string[];
  health_status: string;
  provider: string;
  timestamp: string;
}

const API_BASE = '/api';

export async function publishEvent(
  streamName: string,
  eventType: string,
  payload: Record<string, any>,
  partition: number = 0
): Promise<StreamEvent> {
  const resp = await fetch(`${API_BASE}/events/publish`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      stream_name: streamName,
      event_type: eventType,
      payload,
      partition,
    }),
  });
  if (!resp.ok) {
    throw new Error(`Failed to publish event: ${resp.status}`);
  }
  return resp.json();
}

export async function replayEvents(
  streamName: string = 'telemetry.stream',
  fromOffset: number = 0,
  toOffset?: number
): Promise<StreamEvent[]> {
  const url = toOffset !== undefined
    ? `${API_BASE}/events/replay?stream_name=${encodeURIComponent(streamName)}&from_offset=${fromOffset}&to_offset=${toOffset}`
    : `${API_BASE}/events/replay?stream_name=${encodeURIComponent(streamName)}&from_offset=${fromOffset}`;
  const resp = await fetch(url);
  if (!resp.ok) {
    throw new Error(`Failed to replay events: ${resp.status}`);
  }
  return resp.json();
}

export async function getEventProjection(streamName: string): Promise<StreamProjection> {
  const resp = await fetch(`${API_BASE}/events/projection/${encodeURIComponent(streamName)}`);
  if (!resp.ok) {
    throw new Error(`Failed to get projection: ${resp.status}`);
  }
  return resp.json();
}

export async function listDataLakeObjects(bucket?: string, limit: number = 50): Promise<DataLakeObject[]> {
  const url = bucket
    ? `${API_BASE}/datalake/objects?bucket=${encodeURIComponent(bucket)}&limit=${limit}`
    : `${API_BASE}/datalake/objects?limit=${limit}`;
  const resp = await fetch(url);
  if (!resp.ok) {
    throw new Error(`Failed to list data lake objects: ${resp.status}`);
  }
  return resp.json();
}

export async function putDataLakeObject(
  bucket: string,
  key: string,
  data: any,
  contentType: string = 'application/json',
  metadata?: Record<string, any>
): Promise<DataLakeObject> {
  const resp = await fetch(`${API_BASE}/datalake/objects`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      bucket,
      key,
      data,
      content_type: contentType,
      metadata,
    }),
  });
  if (!resp.ok) {
    throw new Error(`Failed to put data lake object: ${resp.status}`);
  }
  return resp.json();
}

export async function getDataLakeAnalysis(bucket?: string): Promise<DataLakeAnalysis> {
  const url = bucket ? `${API_BASE}/datalake/analysis?bucket=${encodeURIComponent(bucket)}` : `${API_BASE}/datalake/analysis`;
  const resp = await fetch(url);
  if (!resp.ok) {
    throw new Error(`Failed to get data lake analysis: ${resp.status}`);
  }
  return resp.json();
}
