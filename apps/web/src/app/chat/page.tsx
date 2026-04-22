"use client";

import { useCallback, useMemo, useRef, useState } from "react";

import {
  LANGUAGE_CODES,
  LANGUAGE_LABELS,
  LanguageCode,
  getMessages,
} from "@/lib/messages";
import { streamChat } from "@/lib/api";

interface Turn {
  id: string;
  role: "user" | "assistant";
  content: string;
  pending?: boolean;
}

function randomId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export default function ChatPage() {
  const [language, setLanguage] = useState<LanguageCode>("en");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [streaming, setStreaming] = useState(false);
  const threadIdRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const t = useMemo(() => getMessages(language), [language]);

  const submit = useCallback(async () => {
    const message = draft.trim();
    if (!message || streaming) return;

    const userTurn: Turn = { id: randomId(), role: "user", content: message };
    const assistantTurn: Turn = {
      id: randomId(),
      role: "assistant",
      content: "",
      pending: true,
    };

    setTurns((prev) => [...prev, userTurn, assistantTurn]);
    setDraft("");
    setStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      for await (const chunk of streamChat({
        message,
        language,
        threadId: threadIdRef.current,
        signal: controller.signal,
      })) {
        if (chunk.event === "start" && chunk.thread_id) {
          threadIdRef.current = chunk.thread_id;
        } else if (chunk.event === "delta" && chunk.delta) {
          setTurns((prev) =>
            prev.map((turn) =>
              turn.id === assistantTurn.id
                ? { ...turn, content: turn.content + chunk.delta }
                : turn,
            ),
          );
        } else if (chunk.event === "done") {
          setTurns((prev) =>
            prev.map((turn) =>
              turn.id === assistantTurn.id
                ? {
                    ...turn,
                    content: chunk.message ?? turn.content,
                    pending: false,
                  }
                : turn,
            ),
          );
        }
      }
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      setTurns((prev) =>
        prev.map((turn) =>
          turn.id === assistantTurn.id
            ? { ...turn, content: `⚠️ ${reason}`, pending: false }
            : turn,
        ),
      );
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  }, [draft, language, streaming]);

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        void submit();
      }
    },
    [submit],
  );

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-6 px-4 py-6 sm:py-10">
      <header className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">{t.chat.title}</h1>
          <p className="text-sm text-zinc-500">{t.chat.subtitle}</p>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <span className="text-zinc-500">{t.chat.language}</span>
          <select
            className="rounded-md border border-zinc-300 bg-white px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-900"
            value={language}
            onChange={(e) => setLanguage(e.target.value as LanguageCode)}
            disabled={streaming}
          >
            {LANGUAGE_CODES.map((code) => (
              <option key={code} value={code}>
                {LANGUAGE_LABELS[code]}
              </option>
            ))}
          </select>
        </label>
      </header>

      <section className="flex-1 space-y-4 overflow-y-auto">
        {turns.length === 0 ? (
          <div className="rounded-xl border border-dashed border-zinc-300 p-6 text-sm text-zinc-500 dark:border-zinc-700">
            {t.chat.emptyHint}
          </div>
        ) : (
          turns.map((turn) => (
            <article
              key={turn.id}
              className={
                turn.role === "user"
                  ? "ml-auto max-w-[85%] rounded-2xl bg-zinc-900 px-4 py-3 text-white dark:bg-zinc-100 dark:text-zinc-900"
                  : "mr-auto max-w-[85%] rounded-2xl bg-zinc-100 px-4 py-3 text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100"
              }
            >
              <div className="whitespace-pre-wrap leading-6">
                {turn.content || (turn.pending ? t.chat.streaming : "")}
              </div>
            </article>
          ))
        )}
      </section>

      <footer className="sticky bottom-0 bg-white/90 pt-2 backdrop-blur dark:bg-black/80">
        <div className="flex items-end gap-2 rounded-2xl border border-zinc-300 bg-white p-2 shadow-sm dark:border-zinc-700 dark:bg-zinc-900">
          <textarea
            className="flex-1 resize-none bg-transparent p-2 text-base focus:outline-none"
            rows={2}
            placeholder={t.chat.placeholder}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKeyDown}
            disabled={streaming}
          />
          <button
            type="button"
            onClick={() => void submit()}
            disabled={streaming || draft.trim().length === 0}
            className="rounded-xl bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors disabled:opacity-40 hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
          >
            {t.chat.send}
          </button>
        </div>
      </footer>
    </main>
  );
}
