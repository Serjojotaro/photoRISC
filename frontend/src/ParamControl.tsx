import type { ParameterSchema } from "./types";
import styles from "./Editor.module.css";

interface Props {
  name: string;
  schema: ParameterSchema;
  value: unknown;
  onChange: (value: unknown) => void;
}

export default function ParamControl({
  name,
  schema,
  value,
  onChange,
}: Props) {
  const label = schema.title || name;

  if (schema.enum) {
    return (
      <label className={styles.control}>
        <span>{label}</span>
        <select
          value={String(value)}
          onChange={(event) => onChange(event.target.value)}
        >
          {schema.enum.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </label>
    );
  }

  if (schema.type === "boolean") {
    return (
      <label className={`${styles.control} ${styles.checkboxControl}`}>
        <input
          type="checkbox"
          checked={Boolean(value)}
          onChange={(event) => onChange(event.target.checked)}
        />
        <span>{label}</span>
      </label>
    );
  }

  if (schema.type === "number" || schema.type === "integer") {
    const minimum = schema.minimum ?? 0;
    const maximum = schema.maximum ?? 100;
    const step = schema.type === "integer" ? 1 : 0.01;
    return (
      <label className={styles.control}>
        <span className={styles.controlHeading}>
          <span>{label}</span>
          <output>{String(value)}</output>
        </span>
        <input
          type="range"
          min={minimum}
          max={maximum}
          step={step}
          value={Number(value)}
          onChange={(event) => onChange(Number(event.target.value))}
        />
      </label>
    );
  }

  return (
    <label className={styles.control}>
      <span>{label}</span>
      <input
        type="text"
        value={String(value ?? "")}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}
