"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { getCarPageAbsoluteUrl } from "@/lib/car-url";
import Link from "next/link";
import { submitLeadRequest } from "@/lib/lead-client";
import { LEAD_NAME_MAX_LEN, validateLeadFullName, validateLeadPhone } from "@/lib/lead-form-validation";
import { cn } from "@/lib/utils";

type Props = {
  carId: string;
  carTitle: string;
  triggerLabel?: string;
  triggerClassName?: string;
  triggerSize?: "sm" | "default" | "lg";
};

export function CatalogQuickBuyDialog({
  carId,
  carTitle,
  triggerLabel = "Купить",
  triggerClassName,
  triggerSize = "sm",
}: Props) {
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
      "Заявка на покупку из каталога",
      `Автомобиль: ${carTitle}`,
      `Ссылка: ${link}`,
      "",
      `Имя клиента: ${name.trim()}`,
      `Контактный номер: ${phoneCheck.digits}`,
    ].join("\n");

    const result = await submitLeadRequest({
      full_name: name.trim(),
      contact_method: "Звонок по телефону",
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
          variant="default"
          size={triggerSize}
          className={triggerClassName ?? "ms-auto rounded-full px-4 font-semibold shadow-sm"}
        >
          {triggerLabel}
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md" showCloseButton>
        <DialogHeader>
          <DialogTitle>Оставить заявку на покупку</DialogTitle>
          <DialogDescription id={`catalog-buy-desc-${carId}`}>{carTitle}</DialogDescription>
        </DialogHeader>
        <div className="grid gap-3">
          <div className="grid gap-1.5">
            <Label htmlFor={`buy-name-${carId}`}>Имя</Label>
            <Input
              id={`buy-name-${carId}`}
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                if (nameError) setNameError("");
              }}
              placeholder="Ваше имя"
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
            <Label htmlFor={`buy-phone-${carId}`}>Контактный номер</Label>
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
            {status === "sending" ? "Отправка..." : "Отправить"}
          </Button>
          <div className="rounded-xl border border-border/70 bg-muted/25 p-3">
            <label className="flex items-start gap-3 text-xs text-foreground/90">
              <Checkbox
                checked={pdAgree}
                onCheckedChange={(v) => setPdAgree(v === true)}
                className="mt-0.5 border-foreground/25"
                aria-label="Согласие на обработку персональных данных"
              />
              <span className="leading-snug">
                Согласен на обработку персональных данных по{" "}
                <Link
                  href="/privacy"
                  className="font-medium text-primary underline underline-offset-4 hover:text-primary/90"
                >
                  Политике конфиденциальности
                </Link>
                .
              </span>
            </label>
          </div>
          {status === "ok" ? (
            <p className="text-sm font-medium text-emerald-700 dark:text-emerald-400">
              Ваша заявка отправлена, в ближайшее время с вами свяжется менеджер.
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
