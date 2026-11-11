"use client";

import { ChevronDown } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

export function MultiSelect({
  label,
  options,
  value,
  onChange,
  emptyText = "No options",
}: {
  label: string;
  options: { value: string; label: string }[];
  value: string[];
  onChange: (next: string[]) => void;
  emptyText?: string;
}) {
  const toggle = (v: string) => onChange(value.includes(v) ? value.filter((x) => x !== v) : [...value, v]);
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className={cn("h-9", value.length && "border-primary/50")}>
          {label}
          {value.length > 0 && (
            <span className="rounded bg-primary/15 px-1.5 text-[11px] font-semibold text-primary-tint-fg">{value.length}</span>
          )}
          <ChevronDown className="text-muted-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-64 p-1.5">
        {options.length === 0 ? (
          <p className="px-2 py-3 text-sm text-muted-foreground">{emptyText}</p>
        ) : (
          <div className="max-h-72 overflow-y-auto" role="group" aria-label={label}>
            {options.map((o) => {
              const id = `ms-${label}-${o.value}`;
              return (
                <label
                  key={o.value}
                  htmlFor={id}
                  className="flex cursor-pointer items-center gap-2.5 rounded-md px-2 py-1.5 text-sm hover:bg-accent"
                >
                  <Checkbox id={id} checked={value.includes(o.value)} onCheckedChange={() => toggle(o.value)} />
                  <span className="truncate">{o.label}</span>
                </label>
              );
            })}
          </div>
        )}
        {value.length > 0 && (
          <button
            className="mt-1 w-full rounded-md px-2 py-1.5 text-left text-xs text-muted-foreground hover:bg-accent"
            onClick={() => onChange([])}
          >
            Clear selection
          </button>
        )}
      </PopoverContent>
    </Popover>
  );
}
