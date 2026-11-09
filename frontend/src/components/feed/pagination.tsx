"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";

export function Pagination({
  page,
  pages,
  total,
  pageSize,
  onChange,
}: {
  page: number;
  pages: number;
  total: number;
  pageSize: number;
  onChange: (page: number) => void;
}) {
  if (pages <= 1) return null;
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);
  return (
    <nav aria-label="Pagination" className="mt-6 flex items-center justify-between gap-3">
      <p className="text-sm text-muted-foreground">
        <span className="tabular">
          {from}–{to}
        </span>{" "}
        of <span className="tabular">{total.toLocaleString("en")}</span>
      </p>
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => onChange(page - 1)}>
          <ChevronLeft /> Previous
        </Button>
        <span className="hidden text-sm text-muted-foreground sm:inline">
          Page {page} of {pages}
        </span>
        <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => onChange(page + 1)}>
          Next <ChevronRight />
        </Button>
      </div>
    </nav>
  );
}
