import { useId, useState } from "react";

interface Props {
  label: string;
  options: { value: string; label: string }[];
  value: string;
  onChange: (value: string) => void;
  hint?: string;
  required?: boolean;
}

/** Searchable select built on a native input + datalist (keyboard and screen-reader friendly). */
export function SuburbPicker({ label, options, value, onChange, hint, required }: Props) {
  const id = useId();
  const current = options.find((o) => o.value === value)?.label ?? "";
  const [text, setText] = useState(current);
  const [error, setError] = useState<string | null>(null);
  const [lastValue, setLastValue] = useState(value);
  if (value !== lastValue) {
    setLastValue(value);
    setText(current);
  }

  const resolve = (t: string) => {
    const norm = t.trim().toLowerCase();
    return options.find((o) => o.label.toLowerCase() === norm || o.value.toLowerCase() === norm);
  };

  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        type="search"
        list={`${id}-list`}
        value={text}
        autoComplete="off"
        required={required}
        aria-invalid={error ? true : undefined}
        aria-describedby={`${id}-hint`}
        placeholder="Start typing a suburb…"
        onChange={(e) => {
          setText(e.target.value);
          const hit = resolve(e.target.value);
          if (hit) {
            setError(null);
            setLastValue(hit.value);
            onChange(hit.value);
          }
        }}
        onBlur={() => setError(text && !resolve(text) ? "Pick a suburb from the list." : null)}
      />
      <datalist id={`${id}-list`}>
        {options.map((o) => (
          <option key={o.value} value={o.label} />
        ))}
      </datalist>
      <span id={`${id}-hint`} className="hint" role={error ? "alert" : undefined}>
        {error ?? hint}
      </span>
    </div>
  );
}
