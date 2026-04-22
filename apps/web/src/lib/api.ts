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
