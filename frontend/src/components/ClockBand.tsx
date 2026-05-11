import { progressPercent } from "../utils";

interface ClockBandProps {
  label: string;
  value: number;
  max: number;
  detail?: string;
  scope?: string;
  visibility?: string;
  status?: string;
}

export function ClockBand({
  label,
  value,
  max,
  detail,
  scope,
  visibility,
  status,
}: ClockBandProps) {
  const cap = Math.max(max, 1);
  const filled = Math.max(0, Math.min(value, cap));
  const pct = progressPercent(value, cap);
  const warn = pct > 65;
  return (
    <article className="clock-band">
      <header className="clock-band__head">
        <span className="clock-band__label" title={label}>{label}</span>
        <span className="clock-band__count">
          {value}/{cap}
        </span>
      </header>
      <div className="clock-band__bars" aria-hidden="true">
        {Array.from({ length: cap }).map((_, i) => (
          <span
            key={i}
            className={`clock-band__bar${i < filled ? " is-on" : ""}${
              warn ? " is-warn" : ""
            }`}
          />
        ))}
      </div>
      <div className="clock-band__meta">
        {detail && <span>{detail}</span>}
        {scope && <span>· {scope}</span>}
        {visibility && <span>· {visibility}</span>}
        {status && <span>· {status}</span>}
      </div>
    </article>
  );
}
