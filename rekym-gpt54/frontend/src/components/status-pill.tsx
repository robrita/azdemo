import { statusStyles } from "@/theme/tokens";

type StatusPillProps = {
  status: string;
  label?: string;
};

export function StatusPill({ status, label }: StatusPillProps) {
  const styleClass = statusStyles[status] || "badge-primary";
  return <span className={styleClass}>{label || status}</span>;
}