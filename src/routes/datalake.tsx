import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Panel, Mono, Stat } from "@/components/doip/primitives";
import { cn } from "@/lib/utils";
import {
  replayEvents,
  getEventProjection,
  publishEvent,
  listDataLakeObjects,
  getDataLakeAnalysis,
  type StreamEvent,
  type StreamProjection,
  type DataLakeObject,
  type DataLakeAnalysis,
} from "@/services/datalake";
import {
  Database,
  Radio,
  HardDrive,
  Activity,
  Play,
  Send,
  RefreshCw,
  Layers,
  FileJson,
  Hash,
} from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/datalake")({
  head: () => ({
    meta: [
      { title: "Event Streams & Data Lake — DOIP" },
      {
        name: "description",
        content: "Enterprise Kafka-compatible event streaming and operational data lake object storage.",
      },
    ],
  }),
  component: DataLakeDashboard,
});

function DataLakeDashboard() {
  // Streams State
  const [selectedStream, setSelectedStream] = useState("telemetry.stream");
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [projection, setProjection] = useState<StreamProjection | null>(null);
  const [loadingStream, setLoadingStream] = useState(false);

  // Publish Event Form
  const [eventType, setEventType] = useState("POSITION_UPDATE");
  const [payloadText, setPayloadText] = useState('{"unit_id": "UNIT-UAV-1", "speed_kph": 85.0}');
  const [publishing, setPublishing] = useState(false);

  // Data Lake State
  const [objects, setObjects] = useState<DataLakeObject[]>([]);
  const [analysis, setAnalysis] = useState<DataLakeAnalysis | null>(null);
  const [loadingLake, setLoadingLake] = useState(false);

  const fetchStreamData = async (stream: string) => {
    setLoadingStream(true);
    try {
      const [evList, proj] = await Promise.all([
        replayEvents(stream, 0, 50),
        getEventProjection(stream),
      ]);
      setEvents(evList);
      setProjection(proj);
    } catch (err: any) {
      toast.error(`Failed to load stream events: ${err.message}`);
    } finally {
      setLoadingStream(false);
    }
  };

  const fetchLakeData = async () => {
    setLoadingLake(true);
    try {
      const [objList, an] = await Promise.all([
        listDataLakeObjects(undefined, 50),
        getDataLakeAnalysis(),
      ]);
      setObjects(objList);
      setAnalysis(an);
    } catch (err: any) {
      toast.error(`Failed to load data lake objects: ${err.message}`);
    } finally {
      setLoadingLake(false);
    }
  };

  useEffect(() => {
    fetchStreamData(selectedStream);
    fetchLakeData();
  }, [selectedStream]);

  const handlePublish = async () => {
    setPublishing(true);
    try {
      const payload = JSON.parse(payloadText);
      const ev = await publishEvent(selectedStream, eventType, payload, 0);
      toast.success(`Event published with offset #${ev.offset}`);
      fetchStreamData(selectedStream);
    } catch (err: any) {
      toast.error(`Publish error: ${err.message}`);
    } finally {
      setPublishing(false);
    }
  };

  return (
    <div className="space-y-4 p-4 text-[#F2F2F2] max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between border-b border-[#2A2A2A] pb-3 gap-2">
        <div>
          <div className="flex items-center gap-2">
            <Database className="h-5 w-5 text-emerald-400" />
            <h1 className="text-xl font-bold tracking-wider uppercase">Event Streaming & Operational Data Lake</h1>
          </div>
          <p className="text-xs text-[#8A8A8A] mt-0.5">
            Phases 4I & 4J · Kafka-compatible ring-buffered streaming bus and S3/MinIO operational telemetry data lake.
          </p>
        </div>
        <button
          onClick={() => {
            fetchStreamData(selectedStream);
            fetchLakeData();
          }}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-[#161616] hover:bg-[#202020] border border-[#2A2A2A] rounded transition"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh Pipeline
        </button>
      </div>

      {/* KPI Overview */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Panel className="bg-[#0D0D0D] border-[#2A2A2A] p-3">
          <Stat
            label="Total Lake Objects"
            value={analysis?.total_objects ?? objects.length}
            sub="Archived telemetry & briefs"
          />
        </Panel>
        <Panel className="bg-[#0D0D0D] border-[#2A2A2A] p-3">
          <Stat
            label="Data Stored"
            value={`${analysis?.total_size_kb ?? 124.5} KB`}
            sub="S3/MinIO payload volume"
          />
        </Panel>
        <Panel className="bg-[#0D0D0D] border-[#2A2A2A] p-3">
          <Stat
            label="Stream Offset"
            value={`#${projection?.latest_offset ?? 0}`}
            sub={`Buffer: ${projection?.total_events_in_buffer ?? 0} events`}
          />
        </Panel>
        <Panel className="bg-[#0D0D0D] border-[#2A2A2A] p-3">
          <Stat
            label="Storage Health"
            value={analysis?.health_status ?? "ONLINE"}
            sub="Abstracted Object Store"
          />
        </Panel>
      </div>

      {/* Main Grid: Left Event Streams, Right Data Lake Objects */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Left: Event Streaming Bus */}
        <div className="space-y-4">
          <Panel className="bg-[#0D0D0D] border-[#2A2A2A] p-4 space-y-3">
            <div className="flex items-center justify-between border-b border-[#2A2A2A] pb-2">
              <div className="flex items-center gap-2">
                <Radio className="h-4 w-4 text-cyan-400" />
                <span className="text-sm font-semibold uppercase">Event Streaming Platform</span>
              </div>
              <div className="flex gap-1">
                {["telemetry.stream", "threats.stream", "weather.stream", "logistics.stream"].map((s) => (
                  <button
                    key={s}
                    onClick={() => setSelectedStream(s)}
                    className={cn(
                      "px-2 py-0.5 rounded text-[11px] font-mono",
                      selectedStream === s
                        ? "bg-cyan-600 text-white font-semibold"
                        : "bg-[#181818] text-[#8A8A8A] hover:bg-[#222222]"
                    )}
                  >
                    {s.split(".")[0]}
                  </button>
                ))}
              </div>
            </div>

            {/* Stream Materialized State Projection */}
            {projection && (
              <div className="bg-[#141414] border border-[#222222] rounded p-2.5 space-y-1.5 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-white">Stream State Projection:</span>
                  <span className="font-mono text-cyan-400 text-[11px]">
                    Offset #{projection.latest_offset}
                  </span>
                </div>
                <div className="flex flex-wrap gap-2 text-[11px]">
                  {Object.entries(projection.event_types_breakdown).map(([k, count]) => (
                    <span key={k} className="bg-[#1E1E1E] px-2 py-0.5 rounded text-[#C0C0C0] font-mono">
                      {k}: <strong className="text-white">{count}</strong>
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Publish Event Form */}
            <div className="bg-[#141414] border border-[#222222] rounded p-3 space-y-2 text-xs">
              <span className="font-semibold text-white block">Publish Stream Event</span>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[10px] text-[#8A8A8A] block mb-1">Event Type</label>
                  <input
                    type="text"
                    value={eventType}
                    onChange={(e) => setEventType(e.target.value)}
                    className="w-full bg-[#1A1A1A] border border-[#2A2A2A] rounded px-2 py-1 text-xs text-white focus:outline-none"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-[#8A8A8A] block mb-1">Target Stream</label>
                  <input
                    type="text"
                    readOnly
                    value={selectedStream}
                    className="w-full bg-[#1A1A1A] border border-[#2A2A2A] rounded px-2 py-1 text-xs text-[#8A8A8A] font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="text-[10px] text-[#8A8A8A] block mb-1">JSON Payload</label>
                <textarea
                  rows={2}
                  value={payloadText}
                  onChange={(e) => setPayloadText(e.target.value)}
                  className="w-full bg-[#1A1A1A] border border-[#2A2A2A] rounded px-2 py-1 text-xs text-white font-mono focus:outline-none"
                />
              </div>

              <button
                onClick={handlePublish}
                disabled={publishing}
                className="w-full py-1.5 bg-cyan-700 hover:bg-cyan-600 text-white font-semibold text-xs rounded transition flex items-center justify-center gap-1.5"
              >
                <Send className="h-3 w-3" />
                {publishing ? "Publishing..." : "Publish Event"}
              </button>
            </div>

            {/* Replayed Stream Events List */}
            <div className="space-y-1.5 max-h-[340px] overflow-y-auto">
              <span className="text-[11px] font-mono text-[#8A8A8A] block">
                Stream Event Replay ({events.length} Events):
              </span>
              {events.map((ev, i) => (
                <div
                  key={i}
                  className="bg-[#121212] border border-[#222222] rounded p-2 text-xs space-y-1 hover:border-[#333333] transition"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-cyan-400 font-semibold">
                      Offset #{ev.offset}
                    </span>
                    <span className="text-[10px] uppercase font-mono bg-[#1E1E1E] px-1.5 py-0.5 rounded text-amber-300">
                      {ev.event_type}
                    </span>
                  </div>
                  <pre className="text-[10px] text-[#A0A0A0] font-mono overflow-x-auto p-1 bg-[#0A0A0A] rounded">
                    {JSON.stringify(ev.payload)}
                  </pre>
                </div>
              ))}
            </div>
          </Panel>
        </div>

        {/* Right: Operational Data Lake Objects */}
        <div className="space-y-4">
          <Panel className="bg-[#0D0D0D] border-[#2A2A2A] p-4 space-y-3">
            <div className="flex items-center justify-between border-b border-[#2A2A2A] pb-2">
              <div className="flex items-center gap-2">
                <HardDrive className="h-4 w-4 text-emerald-400" />
                <span className="text-sm font-semibold uppercase">Operational Data Lake (S3/MinIO)</span>
              </div>
              <span className="text-[11px] font-mono text-[#8A8A8A]">
                {objects.length} Objects Stored
              </span>
            </div>

            {/* Bucket Distribution Summary */}
            {analysis && (
              <div className="bg-[#141414] border border-[#222222] rounded p-2.5 text-xs space-y-1">
                <span className="font-semibold text-white block">Buckets Distribution:</span>
                <div className="flex flex-wrap gap-2 text-[11px]">
                  {Object.entries(analysis.buckets_distribution).map(([b, count]) => (
                    <span key={b} className="bg-[#1C1C1C] px-2 py-0.5 rounded text-emerald-300 font-mono">
                      {b}: {count}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Objects Table */}
            <div className="overflow-x-auto max-h-[500px]">
              <table className="w-full text-xs text-left">
                <thead className="bg-[#161616] text-[#8A8A8A] uppercase font-mono text-[10px]">
                  <tr>
                    <th className="py-2 px-3">Bucket</th>
                    <th className="py-2 px-3">Key</th>
                    <th className="py-2 px-3">Size</th>
                    <th className="py-2 px-3">ETag</th>
                    <th className="py-2 px-3">Created</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1F1F1F]">
                  {objects.map((obj, i) => (
                    <tr key={i} className="hover:bg-[#141414] transition">
                      <td className="py-2 px-3 font-mono text-emerald-400">{obj.bucket}</td>
                      <td className="py-2 px-3 font-mono text-white">{obj.key}</td>
                      <td className="py-2 px-3 font-mono text-[#A0A0A0]">{obj.size_bytes} B</td>
                      <td className="py-2 px-3 font-mono text-[#777777]">{obj.etag}</td>
                      <td className="py-2 px-3 text-[10px] text-[#888888]">
                        {obj.created_at ? new Date(obj.created_at).toLocaleTimeString() : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
