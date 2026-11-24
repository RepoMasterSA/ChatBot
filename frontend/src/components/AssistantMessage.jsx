import ReactMarkdown from "react-markdown";

function Field({ label, children, testId, className = "" }) {
  return (
    <div className={`meta-field ${className}`}>
      <dt>{label}</dt>
      <dd data-testid={testId}>{children}</dd>
    </div>
  );
}

export default function AssistantMessage({ reply, metadata }) {
  const cached = metadata.resolution_source === "LLM_CACHE";
  const failedKeys = metadata.fallback_attempts;

  return (
    <article className="message assistant" data-testid="assistant-message">
      <div className="message-role">Assistant</div>
      <div className="prose">
        <ReactMarkdown>{reply}</ReactMarkdown>
      </div>

      <dl className="meta">
        <Field label="Source" testId="meta-source" className={cached ? "is-cache" : "is-live"}>
          {metadata.resolution_source}
        </Field>
        <Field label="Model" testId="meta-model">
          {metadata.model}
        </Field>
        <Field label="Latency" testId="meta-latency">
          {metadata.latency_ms} ms
        </Field>
        <Field label="Input tokens" testId="meta-input-tokens">
          {metadata.input_tokens}
        </Field>
        <Field label="Output tokens" testId="meta-output-tokens">
          {metadata.output_tokens}
        </Field>
      </dl>

      <p className="meta-note" data-testid="meta-route">
        {cached
          ? "Served from cache, no provider call."
          : failedKeys > 0
          ? `Answered by ${metadata.key_id} after ${failedKeys} failed ${failedKeys === 1 ? "key" : "keys"}.`
          : `Answered by ${metadata.key_id}.`}
      </p>
    </article>
  );
}
