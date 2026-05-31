"use client";

import { useState } from "react";
import { Button, type buttonVariants } from "@/components/ui/button";
import type { VariantProps } from "class-variance-authority";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { getCarPageAbsoluteUrl } from "@/lib/car-url";
import Link from "next/link";
import { submitLeadRequest } from "@/lib/lead-client";
import { LEAD_NAME_MAX_LEN, validateLeadFullName, validateLeadPhone } from "@/lib/lead-form-validation";
import { useLocaleContext } from "@/components/LocaleProvider";
import { cn } from "@/lib/utils";

type Props = {
  carId: string;
  carTitle: string;
  triggerLabel?: string;
  triggerClassName?: string;
  triggerSize?: "sm" | "default" | "lg";
  triggerVariant?: VariantProps<typeof buttonVariants>["variant"];
};

export function CatalogQuickBuyDialog({
  carId,
  carTitle,
  triggerLabel,
  triggerClassName,
  triggerSize = "sm",
  triggerVariant = "default",
}: Props) {
  const { t } = useLocaleContext();
  const label = triggerLabel ?? t("catalog.quickBuy.trigger");
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [status, setStatus] = useState<"idle" | "sending" | "ok" | "err">("idle");
  const [errText, setErrText] = useState("");
  const [nameError, setNameError] = useState("");
  const [phoneError, setPhoneError] = useState("");
  const [pdAgree, setPdAgree] = useState(false);

  async function submit() {
    setErrText("");
    setNameError("");
    setPhoneError("");

    const nameCheck = validateLeadFullName(name);
    if (!nameCheck.ok) {
      setNameError(nameCheck.message);
      return;
    }
    const phoneCheck = validateLeadPhone(phone);
    if (!phoneCheck.ok) {
      setPhoneError(phoneCheck.message);
      return;
    }

    setStatus("sending");
    const link = getCarPageAbsoluteUrl(carId);
    const message = [
      t("catalog.quickBuy.leadSubject"),
      t("catalog.quickBuy.leadCar", { title: carTitle }),
      t("catalog.quickBuy.leadLink", { link }),
      "",
      t("catalog.quickBuy.leadName", { name: name.trim() }),
      t("catalog.quickBuy.leadPhone", { phone: phoneCheck.digits }),
    ].join("\n");

    const result = await submitLeadRequest({
      full_name: name.trim(),
      contact_method: t("catalog.quickBuy.contactCall"),
      message,
      pd_agree: pdAgree,
    });

    if (!result.ok) {
      setStatus("err");
      setErrText(result.message);
      return;
    }

    setStatus("ok");
    setName("");
    setPhone("");
  }

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button
          type="button"
          variant={triggerVariant}
          size={triggerSize}
          className={triggerClassName ?? "ms-auto rounded-full px-4 font-semibold shadow-sm"}
        >
          {label}
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md" showCloseButton>
        <DialogHeader>
          <DialogTitle>{t("catalog.quickBuy.title")}</DialogTitle>
          <DialogDescription id={`catalog-buy-desc-${carId}`}>{carTitle}</DialogDescription>
        </DialogHeader>
        <div className="grid gap-3">
          <div className="grid gap-1.5">
            <Label htmlFor={`buy-name-${carId}`}>{t("catalog.quickBuy.name")}</Label>
            <Input
              id={`buy-name-${carId}`}
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                if (nameError) setNameError("");
              }}
              placeholder={t("catalog.quickBuy.namePlaceholder")}
              autoComplete="name"
              minLength={2}
              maxLength={LEAD_NAME_MAX_LEN}
              className={cn(nameError && "border-destructive focus-visible:ring-destructive/30")}
              aria-invalid={Boolean(nameError)}
              aria-describedby={nameError ? `buy-name-${carId}-err` : undefined}
            />
            {nameError ? (
              <p id={`buy-name-${carId}-err`} className="text-sm text-destructive" role="alert">
                {nameError}
              </p>
            ) : null}
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor={`buy-phone-${carId}`}>{t("catalog.quickBuy.phone")}</Label>
            <Input
              id={`buy-phone-${carId}`}
              value={phone}
              onChange={(e) => {
                const raw = e.target.value;
                const digits = raw.replace(/\D/g, "");
                setPhone(digits.length <= 11 ? digits : digits.slice(0, 11));
                if (phoneError) setPhoneError("");
              }}
              placeholder="+7 …"
              autoComplete="tel"
              inputMode="tel"
              className={cn(phoneError && "border-destructive focus-visible:ring-destructive/30")}
              aria-invalid={Boolean(phoneError)}
              aria-describedby={phoneError ? `buy-phone-${carId}-err` : undefined}
            />
            {phoneError ? (
              <p id={`buy-phone-${carId}-err`} className="text-sm text-destructive" role="alert">
                {phoneError}
              </p>
            ) : null}
          </div>
          <Button type="button" onClick={submit} disabled={status === "sending" || !pdAgree}>
            {status === "sending" ? t("catalog.quickBuy.sending") : t("catalog.quickBuy.submit")}
          </Button>
          <div className="rounded-xl border border-border/70 bg-muted/25 p-3">
            <label className="flex items-start gap-3 text-xs text-foreground/90">
              <Checkbox
                checked={pdAgree}
                onCheckedChange={(v) => setPdAgree(v === true)}
                className="mt-0.5 border-foreground/25"
                aria-label={t("catalog.quickBuy.pdAria")}
              />
              <span className="leading-snug">
                {t("catalog.quickBuy.pdPrefix")}{" "}
                <Link
                  href="/privacy"
                  className="font-medium text-primary underline underline-offset-4 hover:text-primary/90"
                >
                  {t("buy.privacyLink")}
                </Link>
                .
              </span>
            </label>
          </div>
          {status === "ok" ? (
            <p className="text-sm font-medium text-emerald-700 dark:text-emerald-400">
              {t("catalog.quickBuy.success")}
            </p>
          ) : null}
          {status === "err" ? (
            <p className="text-sm text-destructive [overflow-wrap:anywhere]" role="alert">
              {errText}
            </p>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
