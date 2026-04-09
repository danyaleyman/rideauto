import * as React from "react";
import { Slot } from "radix-ui";
import { ChevronRight, MoreHorizontal } from "lucide-react";

import { cn } from "@/lib/utils";

function Breadcrumb({ className, ...props }: React.ComponentProps<"nav">) {
  return <nav aria-label="Хлебные крошки" className={cn(className)} {...props} />;
}

function BreadcrumbList({ className, ...props }: React.ComponentProps<"ol">) {
  return (
    <ol
      className={cn(
        "flex flex-wrap items-center gap-1.5 break-words text-sm text-muted-foreground sm:gap-2",
        className,
      )}
      {...props}
    />
  );
}

function BreadcrumbItem({ className, ...props }: React.ComponentProps<"li">) {
  return <li className={cn("inline-flex items-center gap-1.5", className)} {...props} />;
}

function BreadcrumbLink({
  className,
  asChild,
  ...props
}: React.ComponentProps<"a"> & { asChild?: boolean }) {
  const Comp = asChild ? Slot.Root : "a";
  return (
    <Comp
      className={cn(
        "font-medium text-foreground/90 underline-offset-4 transition-colors hover:text-foreground hover:underline",
        className,
      )}
      {...props}
    />
  );
}

function BreadcrumbPage({ className, ...props }: React.ComponentProps<"span">) {
  return (
    <span
      role="link"
      aria-disabled="true"
      aria-current="page"
      className={cn("font-medium text-foreground", className)}
      {...props}
    />
  );
}

function BreadcrumbSeparator({ children, className, ...props }: React.ComponentProps<"span">) {
  return (
    <span
      role="presentation"
      aria-hidden="true"
      className={cn("[&>svg]:size-3.5", className)}
      {...props}
    >
      {children ?? <ChevronRight className="text-muted-foreground/80 rtl:rotate-180" />}
    </span>
  );
}

function BreadcrumbEllipsis({ className, ...props }: React.ComponentProps<"span">) {
  return (
    <span
      role="presentation"
      aria-hidden="true"
      className={cn("flex size-9 items-center justify-center", className)}
      {...props}
    >
      <MoreHorizontal className="size-4" />
      <span className="sr-only">Ещё</span>
    </span>
  );
}

export {
  Breadcrumb,
  BreadcrumbList,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbPage,
  BreadcrumbSeparator,
  BreadcrumbEllipsis,
};
