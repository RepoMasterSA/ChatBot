import { useEffect, useRef, useState } from "react";
import AssistantMessage from "./components/AssistantMessage.jsx";
import Composer from "./components/Composer.jsx";
import SessionSettings from "./components/SessionSettings.jsx";
import { sendMessage } from "./api.js";
import { newSessionId } from "./session.js";

export default function App() {
  const [sessionId, setSessionId] = useState(newSessionId);
  const [items, setItems] = useState([]); // {id, kind: user|assistant|error, ...}
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [systemPrompt, setSystemPrompt] = useState("");
  const [simulateFailure, setSimulateFailure] = useState("");
  const endRef = useRef(null);
  const counter = useRef(0);

  const nextId = () => `m${++counter.current}`;

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [items, loading]);

  async function handleSend() {
    const message = draft.trim();
    if (!message || loading) return;

    setDraft("");
    setItems((prev) => [...prev, { id: nextId(), kind: "user", text: message }]);
    setLoading(true);

    try {
      const data = await sendMessage({
        sessionId,
        message,
        systemPrompt: systemPrompt.trim(),
        simulateFailure: simulateFailure.trim(),
      });
      setItems((prev) => [
        ...prev,
        { id: nextId(), kind: "assistant", reply: data.reply, metadata: data.metadata },
      ]);
    } catch (error) {
      setItems((prev) => [...prev, { id: nextId(), kind: "error", text: error.message }]);
    } finally {
      setLoading(false);
    }
  }

  function startNewSession() {
    setSessionId(newSessionId());
    setItems([]);
    setDraft("");
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-inner">
          <h1>Chat Console</h1>
          <div className="topbar-session">
            <span className="session-label">Session</span>
            <code data-testid="session-id">{sessionId}</code>
            <button type="button" className="ghost" onClick={startNewSession}>
              New session
            </button>
          </div>
        </div>
      </header>

      <main className="thread">
        <div className="thread-inner">
          <SessionSettings
            open={settingsOpen}
            onToggle={() => setSettingsOpen((v) => !v)}
            systemPrompt={systemPrompt}
            onSystemPrompt={setSystemPrompt}
            simulateFailure={simulateFailure}
            onSimulateFailure={setSimulateFailure}
          />

          {items.length === 0 && !loading && (
            <div className="empty">
              <h2>Start a conversation</h2>
              <p>
                Each reply shows where it came from, which model answered, how long it took and
                how many tokens the request used.
              </p>
            </div>
          )}

          {items.map((item) => {
            if (item.kind === "user") {
              return (
                <div key={item.id} className="message user" data-testid="user-message">
                  {item.text}
                </div>
              );
            }
            if (item.kind === "error") {
              return (
                <div key={item.id} className="message notice" role="alert" data-testid="error-message">
                  {item.text}
                </div>
              );
            }
            return <AssistantMessage key={item.id} reply={item.reply} metadata={item.metadata} />;
          })}

          {loading && (
            <div className="pending" role="status">
              Waiting for a response<span className="dots" aria-hidden="true" />
            </div>
          )}
          <div ref={endRef} />
        </div>
      </main>

      <footer className="dock">
        <div className="dock-inner">
          <Composer value={draft} onChange={setDraft} onSend={handleSend} disabled={loading} />
        </div>
      </footer>
    </div>
  );
}
