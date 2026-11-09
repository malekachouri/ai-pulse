import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 whitespace-nowrap rounded-md border px-2 py-0.5 text-[11px] font-medium [&_svg]:size-3",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary/15 text-primary dark:text-blue-300",
        secondary: "border-transparent bg-secondary text-secondary-foreground",
        outline: "text-muted-foreground",
        violet: "border-transparent bg-brand-violet/15 text-violet-700 dark:text-violet-300",
        demo: "border-amber-500/40 bg-amber-500/15 font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-300",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

function Badge({ className, variant, ...props }: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return <span data-slot="badge" className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
