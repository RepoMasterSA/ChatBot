export default function SessionSettings({
  open,
  onToggle,
  systemPrompt,
  onSystemPrompt,
  simulateFailure,
  onSimulateFailure,
}) {
  return (
    <section className="settings">
      <button
        type="button"
        className="settings-toggle"
        aria-expanded={open}
        onClick={onToggle}
      >
        Session settings
        <span className={`chevron ${open ? "open" : ""}`} aria-hidden="true" />
      </button>

      {open && (
        <div className="settings-body">
          <label htmlFor="system-prompt">System prompt</label>
          <textarea
            id="system-prompt"
            data-testid="system-prompt-input"
            rows={3}
            placeholder="Optional. Overrides the default instructions for this session."
            value={systemPrompt}
            onChange={(e) => onSystemPrompt(e.target.value)}
          />

          <label htmlFor="simulate-failure">Simulate key failures</label>
          <input
            id="simulate-failure"
            data-testid="simulate-failure-input"
            type="text"
            placeholder="key_1=429   or   *=503"
            value={simulateFailure}
            onChange={(e) => onSimulateFailure(e.target.value)}
          />
          <p className="hint">
            Sent as the X-Simulate-Failure header on each message. Works only when the backend
            has failure simulation enabled.
          </p>
        </div>
      )}
    </section>
  );
}
