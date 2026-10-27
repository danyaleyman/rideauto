"use client"

import * as React from "react"

import { useLocaleContext } from "@/components/LocaleProvider"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { ChevronLeftIcon, ChevronRightIcon, MoreHorizontalIcon } from "lucide-react"

function Pagination({
  className,
  "aria-label": ariaLabel,
  ...props
}: React.ComponentProps<"nav">) {
  const { t } = useLocaleContext();
  return (
    <nav
      role="navigation"
      aria-label={ariaLabel ?? t("common.pagination")}
      data-slot="pagination"
      className={cn("mx-auto flex w-full justify-center", className)}
      {...props}
    />
  )
}

function PaginationContent({
  className,
  ...props
}: React.ComponentProps<"ul">) {
  return (
    <ul
      data-slot="pagination-content"
      className={cn("flex items-center gap-1", className)}
      {...props}
    />
  )
}

function PaginationItem({ ...props }: React.ComponentProps<"li">) {
  return <li data-slot="pagination-item" {...props} />
}

type PaginationLinkProps = {
  isActive?: boolean
} & Pick<React.ComponentProps<typeof Button>, "size"> &
  React.ComponentProps<"a">

function PaginationLink({
  className,
  isActive,
  size = "icon",
  ...props
}: PaginationLinkProps) {
  return (
    <Button
      asChild
      variant={isActive ? "outline" : "ghost"}
      size={size}
      className={cn("max-lg:min-h-11 max-lg:min-w-11", className)}
    >
      <a
        aria-current={isActive ? "page" : undefined}
        data-slot="pagination-link"
        data-active={isActive}
        {...props}
      />
    </Button>
  )
}

function PaginationPrevious({
  className,
  text,
  ...props
}: React.ComponentProps<typeof PaginationLink> & { text?: string }) {
  const { t } = useLocaleContext();
  return (
    <PaginationLink
      aria-label={t("common.pagePrev")}
      size="default"
      className={cn("ps-2!", className)}
      {...props}
    >
      <ChevronLeftIcon data-icon="inline-start" className="rtl:rotate-180" aria-hidden />
      <span className="hidden sm:block">{text ?? t("common.pageBack")}</span>
    </PaginationLink>
  )
}

function PaginationNext({
  className,
  text,
  ...props
}: React.ComponentProps<typeof PaginationLink> & { text?: string }) {
  const { t } = useLocaleContext();
  return (
    <PaginationLink
      aria-label={t("common.pageNext")}
      size="default"
      className={cn("pe-2!", className)}
      {...props}
    >
      <span className="hidden sm:block">{text ?? t("common.pageForward")}</span>
      <ChevronRightIcon data-icon="inline-end" className="rtl:rotate-180" aria-hidden />
    </PaginationLink>
  )
}

function PaginationEllipsis({
  className,
  label,
  ...props
}: React.ComponentProps<"span"> & { label?: string }) {
  const { t } = useLocaleContext();
  return (
    <span
      aria-hidden
      data-slot="pagination-ellipsis"
      className={cn(
        "flex size-9 max-lg:min-h-11 max-lg:min-w-11 items-center justify-center [&_svg:not([class*='size-'])]:size-4",
        className
      )}
      {...props}
    >
      <MoreHorizontalIcon
      />
      <span className="sr-only">{label ?? t("common.pageSkipped")}</span>
    </span>
  )
}

export {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
}
