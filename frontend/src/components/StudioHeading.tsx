import { ReactNode } from "react";

export function StudioHeading({
  number,
  label,
  title,
  accent,
  description,
  action,
}: {
  number: string;
  label: string;
  title: string;
  accent: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <header className="studio-heading">
      <div className="studio-kicker">
        <span>JIALIE / {label}</span>
        <span>{number} — WORKSPACE</span>
      </div>
      <div className="studio-heading-body">
        <div>
          <h1>
            {title}
            <em>{accent}</em>
          </h1>
          <p>{description}</p>
        </div>
        {action && <div className="studio-heading-action">{action}</div>}
      </div>
    </header>
  );
}
