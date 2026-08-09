"use client";

import { AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ErrorStateProps {
  title?: string;
  message: string;
  requestId?: string | null;
  onRetry?: () => void;
  className?: string;
}

// Estado de erro: role="alert" (leitor de tela anuncia), ref discreta p/ suporte
// achar o log (X-Request-ID), e acao de tentar de novo.
export function ErrorState({
  title = "Algo deu errado",
  message,
  requestId,
  onRetry,
  className,
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-lg border border-border bg-surface px-6 py-12 text-center",
        className
      )}
    >
      <AlertCircle className="h-10 w-10 text-error" aria-hidden />
      <h3 className="text-h3 text-text">{title}</h3>
      <p className="max-w-sm text-body text-text-muted">{message}</p>
      {requestId && <p className="text-caption text-text-muted">ref: {requestId}</p>}
      {onRetry && (
        <Button variant="outline" onClick={onRetry}>
          Tentar de novo
        </Button>
      )}
    </div>
  );
}
