import { useEffect, useRef } from "react";

const MAX = 4000;

export default function Composer({ value, onChange, onSend, disabled }) {
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [value]);

  const canSend = !disabled && value.trim().length > 0 && value.length <= MAX;

  function onKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (canSend) onSend();
    }
  }

  return (
    <div className="composer">
      <textarea
        ref={ref}
        data-testid="chat-input"
        aria-label="Message"
        placeholder="Write a message"
        rows={1}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
      />
      <div className="composer-actions">
        <span className={`counter ${value.length > MAX ? "over" : ""}`}>
          {value.length > 3500 ? `${value.length} / ${MAX}` : "Enter to send, Shift+Enter for a new line"}
        </span>
        <button type="button" data-testid="send-button" onClick={onSend} disabled={!canSend}>
          Send
        </button>
      </div>
    </div>
  );
}
