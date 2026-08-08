import * as React from "react";
import { SearchX, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

// Estado "sem resultados": mensagem clara + caminho de saida (action opcional).
export function EmptyState({
  icon: Icon = SearchX,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-lg border border-border bg-surface px-6 py-12 text-center",
        className
      )}
    >
      <Icon className="h-10 w-10 text-text-muted" aria-hidden />
      <h3 className="text-h3 text-text">{title}</h3>
      {description && <p className="max-w-sm text-body text-text-muted">{description}</p>}
      {action}
    </div>
  );
}