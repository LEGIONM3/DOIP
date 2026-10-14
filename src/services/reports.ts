/**
 * Operational Reporting Service (Phase 5K)
 */

export interface OperationalReport {
  id: string;
  report_type: 'sitrep' | 'mission_aar' | 'campaign_assessment' | 'threat_advisory';
  title: string;
  content_md: string;
  data?: Record<string, any>;
  created_at: string;
}

const API_BASE = '/api';

export async function generateReport(
  reportType: string = 'sitrep',
  theater?: string,
  missionId?: string
): Promise<OperationalReport> {
  const resp = await fetch(`${API_BASE}/reports/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ report_type: reportType, theater, mission_id: missionId }),
  });
  if (!resp.ok) throw new Error(`Failed to generate report: ${resp.statusText}`);
  return resp.json();
}

export async function listReports(reportType?: string): Promise<OperationalReport[]> {
  const params = new URLSearchParams();
  if (reportType) params.set('report_type', reportType);
  const resp = await fetch(`${API_BASE}/reports?${params.toString()}`);
  if (!resp.ok) throw new Error(`Failed to list reports: ${resp.statusText}`);
  return resp.json();
}

export async function getReport(reportId: string): Promise<OperationalReport> {
  const resp = await fetch(`${API_BASE}/reports/${reportId}`);
  if (!resp.ok) throw new Error(`Failed to get report: ${resp.statusText}`);
  return resp.json();
}
