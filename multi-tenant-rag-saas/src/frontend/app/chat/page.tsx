/**
 * Chat page (Next.js 15 App Router, React 19).
 *
 * Client component that streams assistant tokens over Socket.IO and
 * renders source citations from the RAG retrieval alongside the
 * answer. This is a public sketch; the production component handles
 * retries, backpressure, partial-response recovery, and optimistic
 * UI updates.
 *
 * TODO: see private repo for full impl.
 */
"use client";

import { useEffect, useRef, useState } from "react";
import { io, type Socket } from "socket.io-client";

type Source = { doc_id: string; chunk_idx: number; title: string; score: number };
type Message = {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
};

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const socketRef = useRef<Socket | null>(null);

  useEffect(() => {
    const socket = io(process.env.NEXT_PUBLIC_APP_ORIGIN!, {
      path: "/socket.io",
      // TODO: see private repo for JWT handshake
    });
    socketRef.current = socket;

    socket.on("token", (t: string) => {
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.role !== "assistant") return prev;
        return [...prev.slice(0, -1), { ...last, content: last.content + t }];
      });
    });

    socket.on("sources", (sources: Source[]) => {
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.role !== "assistant") return prev;
        return [...prev.slice(0, -1), { ...last, sources }];
      });
    });

    socket.on("done", () => setStreaming(false));

    return () => {
      socket.disconnect();
    };
  }, []);

  function send() {
    if (!input.trim() || streaming) return;
    const user: Message = { role: "user", content: input };
    const assistant: Message = { role: "assistant", content: "" };
    setMessages((prev) => [...prev, user, assistant]);
    setInput("");
    setStreaming(true);
    socketRef.current?.emit("chat:send", { content: user.content });
  }

  return (
    <main className="mx-auto max-w-3xl p-6">
      {/* Full layout, Shadcn message bubbles, and citation rail live
          in the private repo. TODO: see private repo for full impl. */}
      <div className="space-y-4">
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "text-right" : ""}>
            <p>{m.content}</p>
            {m.sources && (
              <ul className="mt-2 text-xs text-slate-500">
                {m.sources.map((s) => (
                  <li key={`${s.doc_id}-${s.chunk_idx}`}>
                    {s.title} (score {s.score.toFixed(2)})
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>
      <form
        className="mt-6 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
      >
        <input
          className="flex-1 rounded border p-2"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about your docs..."
        />
        <button
          type="submit"
          className="rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-50"
          disabled={streaming || !input.trim()}
        >
          Send
        </button>
      </form>
    </main>
  );
}
