export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type DocumentKind =
  | "payslip"
  | "receipt"
  | "bank_statement"
  | "cac_certificate"
  | "unknown";

export interface UploadedDocument {
  id: string;
  kind: DocumentKind;
  filename: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
  extraction: Record<string, unknown> | null;
  extraction_error: string | null;
}

export async function uploadDocument({
  file,
  kind,
  threadId,
  signal,
}: {
  file: File;
  kind: DocumentKind;
  threadId?: string | null;
  signal?: AbortSignal;
}): Promise<UploadedDocument> {
  const form = new FormData();
  form.append("file", file);
  form.append("kind", kind);
  if (threadId) form.append("thread_id", threadId);

  const response = await fetch(`${API_BASE}/v1/documents`, {
    method: "POST",
    body: form,
    signal,
  });

  if (!response.ok) {
    const detail = await response
      .json()
      .then((b) => b.detail ?? response.statusText)
      .catch(() => response.statusText);
    throw new Error(`upload failed (${response.status}): ${detail}`);
  }
  return response.json();
}

// ---------------------------------------------------------------------------
// Filings (Phase 4)
// ---------------------------------------------------------------------------

export type AuditStatus = "pending" | "green" | "yellow" | "red";
export type AuditSeverity = "info" | "warn" | "error";

export interface AuditFinding {
  code: string;
  severity: AuditSeverity;
  message: string;
  field_path: string | null;
}

export interface AuditReport {
  status: Exclude<AuditStatus, "pending">;
  findings: AuditFinding[];
}

export interface FilingRecord {
  id: string;
  user_id: string | null;
  tax_year: number;
  return: Record<string, unknown>;
  audit_status: AuditStatus;
  audit: AuditReport | null;
  pack_ready: boolean;
  finalized_at: string | null;
  created_at: string;
  updated_at: string;
}

async function _json<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    const detail = await resp
      .json()
      .then((b) => b.detail ?? resp.statusText)
      .catch(() => resp.statusText);
    throw new Error(`${resp.status}: ${detail}`);
  }
  return resp.json();
}

export async function getFiling(id: string): Promise<FilingRecord> {
  return _json(await fetch(`${API_BASE}/v1/filings/${id}`));
}

export async function runAudit(
  id: string,
): Promise<{ filing: FilingRecord; audit: AuditReport }> {
  return _json(
    await fetch(`${API_BASE}/v1/filings/${id}/audit`, { method: "POST" }),
  );
}

export async function buildFilingPack(
  id: string,
): Promise<{ filing: FilingRecord; pack: Record<string, unknown> }> {
  return _json(
    await fetch(`${API_BASE}/v1/filings/${id}/pack`, { method: "POST" }),
  );
}

export function filingPackDownloadUrl(
  id: string,
  format: "pdf" | "json",
): string {
  return `${API_BASE}/v1/filings/${id}/pack.${format}`;
}

// ---------------------------------------------------------------------------
// Identity (Phase 5)
// ---------------------------------------------------------------------------

export interface IdentityVerificationResult {
  verified: boolean;
  aggregator: string;
  nin_hash: string;
  full_name: string | null;
  first_name: string | null;
  middle_name: string | null;
  last_name: string | null;
  state_of_origin: string | null;
  name_match:
    | {
        ok: boolean;
        mode: "strict" | "fuzzy";
        similarity?: number;
        declared?: string;
        record?: string;
        missing_tokens?: string[];
      }
    | null;
  name_match_status: "strict" | "fuzzy" | "mismatch" | null;
  error: string | null;
  attempts: number;
  consent_log_id: string | null;
}

export async function verifyIdentity(input: {
  nin: string;
  consent: boolean;
  declared_name?: string;
  purpose?: string;
  thread_id?: string | null;
}): Promise<IdentityVerificationResult> {
  const response = await fetch(`${API_BASE}/v1/identity/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });

  if (!response.ok) {
    const detail = await response
      .json()
      .then((b) => b.detail ?? response.statusText)
      .catch(() => response.statusText);
    throw new Error(`${response.status}: ${detail}`);
  }
  return response.json();
}

// ---------------------------------------------------------------------------
// Memory (Phase 8 + P8.10)
// ---------------------------------------------------------------------------

export interface YearlyFact {
  id: string;
  tax_year: number;
  fact_type: string;
  value: string;
  value_kind: string;
  unit: string;
  source: string;
  label: string | null;
  meta: Record<string, unknown> | null;
  recorded_at: string;
  filing_id: string | null;
}

export interface AnomalyFinding {
  fact_type: string;
  severity: "info" | "watch" | "alert";
  prior_year: number;
  current_year: number;
  prior_value: string;
  current_value: string;
  pct_change: string;
  message: string;
}

export interface MidYearNudge {
  code: string;
  severity: "info" | "watch" | "alert";
  message: string;
  meta: Record<string, string>;
}

export async function getFacts(params: {
  nin_hash?: string | null;
  tax_year?: number;
  fact_type?: string;
  limit?: number;
}): Promise<{ facts: YearlyFact[] }> {
  const qs = new URLSearchParams();
  if (params.nin_hash) qs.set("nin_hash", params.nin_hash);
  if (params.tax_year !== undefined) qs.set("tax_year", String(params.tax_year));
  if (params.fact_type) qs.set("fact_type", params.fact_type);
  if (params.limit) qs.set("limit", String(params.limit));
  return _json(await fetch(`${API_BASE}/v1/memory/facts?${qs.toString()}`));
}

export async function recallMemory(params: {
  q: string;
  nin_hash?: string | null;
  limit?: number;
}): Promise<{ facts: YearlyFact[]; mode?: string }> {
  const qs = new URLSearchParams({ q: params.q });
  if (params.nin_hash) qs.set("nin_hash", params.nin_hash);
  if (params.limit) qs.set("limit", String(params.limit));
  return _json(await fetch(`${API_BASE}/v1/memory/recall?${qs.toString()}`));
}

export async function getAnomalies(params: {
  current_year: number;
  nin_hash?: string | null;
  prior_year?: number;
}): Promise<{ findings: AnomalyFinding[] }> {
  const qs = new URLSearchParams({ current_year: String(params.current_year) });
  if (params.nin_hash) qs.set("nin_hash", params.nin_hash);
  if (params.prior_year !== undefined) qs.set("prior_year", String(params.prior_year));
  return _json(await fetch(`${API_BASE}/v1/memory/anomalies?${qs.toString()}`));
}

export async function getNudges(params: {
  current_year: number;
  ytd_gross: string | number;
  month: number;
  nin_hash?: string | null;
  prior_year?: number;
}): Promise<{ nudges: MidYearNudge[] }> {
  const qs = new URLSearchParams({
    current_year: String(params.current_year),
    ytd_gross: String(params.ytd_gross),
    month: String(params.month),
  });
  if (params.nin_hash) qs.set("nin_hash", params.nin_hash);
  if (params.prior_year !== undefined) qs.set("prior_year", String(params.prior_year));
  return _json(await fetch(`${API_BASE}/v1/memory/nudges?${qs.toString()}`));
}

// ---------------------------------------------------------------------------
// NGO filings (Phase 11)
// ---------------------------------------------------------------------------

export type NgoPurpose =
  | "charitable"
  | "educational"
  | "religious"
  | "scientific"
  | "cultural"
  | "social_welfare"
  | "other";

export type NgoWhtRecipient =
  | "individual"
  | "corporate"
  | "partnership"
  | "foreign_entity"
  | "other";

export interface NgoReturn {
  tax_year: number;
  period_start: string;
  period_end: string;
  organization: {
    cac_part_c_rc: string;
    legal_name: string;
    trade_name?: string | null;
    exemption_reference?: string | null;
    purpose: NgoPurpose;
    registered_address?: string | null;
    email?: string | null;
    phone?: string | null;
  };
  income: {
    local_donations?: string | number;
    foreign_donations?: string | number;
    government_grants?: string | number;
    foundation_grants?: string | number;
    program_income?: string | number;
    investment_income?: string | number;
    other_income?: string | number;
  };
  expenditure: {
    program_expenses?: string | number;
    administrative?: string | number;
    fundraising?: string | number;
    other?: string | number;
  };
  wht_schedule: Array<{
    period_month: number;
    transaction_class: string;
    recipient_category: NgoWhtRecipient;
    gross_amount: string | number;
    wht_amount: string | number;
    recipient_reference?: string | null;
    remittance_receipt?: string | null;
  }>;
  supporting_document_ids?: string[];
  exemption_status_declaration: boolean;
  declaration: boolean;
  notes?: string | null;
}

export interface NgoFilingRecord {
  id: string;
  tax_year: number;
  tax_kind: string;
  return: Record<string, unknown>;
  audit_status: AuditStatus;
  audit: AuditReport | null;
  pack_ready: boolean;
  finalized_at: string | null;
  created_at: string;
  updated_at: string;
}

export async function createNgoFiling(
  body: NgoReturn,
): Promise<NgoFilingRecord> {
  const r = await fetch(`${API_BASE}/v1/ngo-filings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return _json(r);
}

export async function getNgoFiling(id: string): Promise<NgoFilingRecord> {
  return _json(await fetch(`${API_BASE}/v1/ngo-filings/${id}`));
}

export async function auditNgoFiling(
  id: string,
): Promise<{ filing: NgoFilingRecord; audit: AuditReport }> {
  return _json(
    await fetch(`${API_BASE}/v1/ngo-filings/${id}/audit`, { method: "POST" }),
  );
}

export async function buildNgoPack(
  id: string,
): Promise<{ filing: NgoFilingRecord; pack: Record<string, unknown> }> {
  return _json(
    await fetch(`${API_BASE}/v1/ngo-filings/${id}/pack`, { method: "POST" }),
  );
}

export function ngoPackDownloadUrl(id: string, format: "pdf" | "json"): string {
  return `${API_BASE}/v1/ngo-filings/${id}/pack.${format}`;
}

// ---------------------------------------------------------------------------
// SME calculators (Phase 9 preview — placeholder statutory data)
// ---------------------------------------------------------------------------

export interface CITResult {
  annual_turnover: string;
  assessable_profit: string;
  tier: string;
  cit_rate: string;
  cit_amount: string;
  tertiary_rate: string;
  tertiary_amount: string;
  total_payable: string;
  notes: string[];
  statutory_source: string;
  statutory_is_placeholder: boolean;
}

export interface WHTResult {
  transaction_class: string;
  gross_amount: string;
  wht_rate: string;
  wht_amount: string;
  net_payable: string;
  statutory_source: string;
  statutory_is_placeholder: boolean;
  error?: string;
  known_classes?: string[];
}

export async function calcCit(input: {
  annual_turnover: number | string;
  assessable_profit: number | string;
  include_tertiary?: boolean;
}): Promise<CITResult> {
  return _json(
    await fetch(`${API_BASE}/v1/sme/calc-cit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  );
}

export async function calcWht(input: {
  gross_amount: number | string;
  transaction_class: string;
}): Promise<WHTResult> {
  return _json(
    await fetch(`${API_BASE}/v1/sme/calc-wht`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  );
}

export async function listWhtClasses(): Promise<{
  classes: string[];
  statutory_is_placeholder: boolean;
}> {
  return _json(await fetch(`${API_BASE}/v1/sme/wht-classes`));
}

export type ChatStreamEvent = "start" | "delta" | "done";

export interface ChatStreamChunk {
  event: ChatStreamEvent;
  thread_id: string;
  delta?: string;
  message?: string;
  language?: string;
  model?: string;
  input_tokens?: number;
  output_tokens?: number;
  cache_read_tokens?: number;
  cache_creation_tokens?: number;
}

/**
 * Consume a `text/event-stream` response and yield typed ChatStreamChunks.
 * Works against POST /v1/chat/stream on the FastAPI backend.
 */
export async function* streamChat({
  message,
  language,
  threadId,
  signal,
}: {
  message: string;
  language: string;
  threadId: string | null;
  signal?: AbortSignal;
}): AsyncGenerator<ChatStreamChunk, void, unknown> {
  const response = await fetch(`${API_BASE}/v1/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      language,
      thread_id: threadId,
    }),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new Error(`chat stream failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const rawFrame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);

      let eventName: ChatStreamEvent | null = null;
      let dataLine: string | null = null;
      for (const line of rawFrame.split("\n")) {
        if (line.startsWith("event:")) {
          eventName = line.slice("event:".length).trim() as ChatStreamEvent;
        } else if (line.startsWith("data:")) {
          dataLine = line.slice("data:".length).trim();
        }
      }
      if (eventName && dataLine) {
        try {
          const parsed = JSON.parse(dataLine) as ChatStreamChunk;
          yield parsed;
        } catch {
          // ignore malformed frames
        }
      }

      boundary = buffer.indexOf("\n\n");
    }
  }
}
