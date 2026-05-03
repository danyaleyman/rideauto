"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import Link from "next/link";
import { LeadContactMethodField } from "@/components/buy/LeadContactMethodField";
import { leadContactMethodLabel, type LeadContactMethodValue } from "@/lib/lead-contact-options";
import { submitLeadRequest } from "@/lib/lead-client";
import { LEAD_MESSAGE_MIN_LEN, validateLeadFullName } from "@/lib/lead-form-validation";

export function OrderLeadForm() {
  const [fullName, setFullName] = useState("");
  const [contactMethod, setContactMethod] = useState<LeadContactMethodValue>("telegram");
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState<"idle" | "sending" | "ok" | "err">("idle");
  const [errText, setErrText] = useState("");
  const [fullNameError, setFullNameError] = useState("");
  const [messageError, setMessageError] = useState("");
  const [pdAgree, setPdAgree] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErrText("");
    setFullNameError("");
    setMessageError("");

    const nameCheck = validateLeadFullName(fullName);
    if (!nameCheck.ok) {
      setFullNameError(nameCheck.message);
      return;
    }
    if (message.trim().length < LEAD_MESSAGE_MIN_LEN) {
      setMessageError(`Опишите запрос не короче ${LEAD_MESSAGE_MIN_LEN} символов`);
      return;
    }

    setStatus("sending");
    const result = await submitLeadRequest({
      full_name: fullName.trim(),
      contact_method: leadContactMethodLabel(contactMethod),
      message: message.trim(),
      pd_agree: pdAgree,
    });

    if (!result.ok) {
      setStatus("err");
      setErrText(result.message);
      return;
    }

    setStatus("ok");
    setFullName("");
    setMessage("");
  }

  return (
    <section
      id="order-lead"
      className="mt-10 scroll-mt-24 rounded-2xl border border-border/60 bg-card/80 p-6 shadow-sm ring-1 ring-black/[0.04] dark:ring-white/[0.06] sm:p-8"
      aria-labelledby="order-lead-heading"
    >
      <h2 id="order-lead-heading" className="text-xl font-semibold tracking-tight text-foreground">
        Оставить заявку
      </h2>
      <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
        Заполните форму — ответим и подскажем по срокам и стоимости. Заявка уходит на почту менеджера.
      </p>

      <form onSubmit={onSubmit} className="mt-6 grid max-w-xl gap-5">
        <div className="grid gap-2">
          <Label htmlFor="lead-full-name">ФИО</Label>
          <Input
            id="lead-full-name"
            name="full_name"
            autoComplete="name"
            required
            minLength={2}
            maxLength={100}
            value={fullName}
            onChange={(e) => {
              setFullName(e.target.value);
              if (fullNameError) setFullNameError("");
            }}
            placeholder="Иванов Иван Иванович"
            className={cn("rounded-2xl", fullNameError && "border-destructive focus-visible:ring-destructive/30")}
            aria-invalid={Boolean(fullNameError)}
            aria-describedby={fullNameError ? "lead-full-name-error" : undefined}
          />
          {fullNameError ? (
            <p id="lead-full-name-error" className="text-sm text-destructive" role="alert">
              {fullNameError}
            </p>
          ) : null}
        </div>

        <LeadContactMethodField
          id="lead-contact"
          value={contactMethod}
          onChange={(v) => setContactMethod(v)}
          disabled={status === "sending"}
        />

        <div className="grid gap-2">
          <Label htmlFor="lead-message">Автомобиль и пожелания</Label>
          <textarea
            id="lead-message"
            name="message"
            required
            minLength={10}
            maxLength={8000}
            rows={5}
            value={message}
            onChange={(e) => {
              setMessage(e.target.value);
              if (messageError) setMessageError("");
            }}
            placeholder="Опишите, какой автомобиль интересует (марка, год, бюджет), с какого рынка (Корея / Китай) или вставьте ссылку на объявление."
            className={cn(
              "w-full min-w-0 resize-y rounded-2xl border border-transparent bg-input/50 px-3 py-2.5 text-base outline-none transition-[color,box-shadow,background-color]",
              "placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30 md:text-sm",
              messageError && "border-destructive focus-visible:ring-destructive/30",
            )}
            aria-invalid={Boolean(messageError)}
            aria-describedby={messageError ? "lead-message-error" : undefined}
          />
          {messageError ? (
            <p id="lead-message-error" className="text-sm text-destructive" role="alert">
              {messageError}
            </p>
          ) : null}
        </div>

        <div className="rounded-xl border border-border/70 bg-muted/25 p-3 sm:p-4">
          <label className="flex items-start gap-3 text-sm text-foreground/90">
            <Checkbox
              checked={pdAgree}
              onCheckedChange={(v) => setPdAgree(v === true)}
              className="mt-0.5 border-foreground/25"
              aria-label="Согласие на обработку персональных данных"
            />
            <span className="leading-snug">
              Даю согласие на обработку персональных данных в соответствии с{" "}
              <Link
                href="/privacy"
                className="font-medium text-primary underline underline-offset-4 hover:text-primary/90"
              >
                Политикой конфиденциальности
              </Link>
              .
            </span>
          </label>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <Button type="submit" size="lg" className="rounded-2xl" disabled={status === "sending" || !pdAgree}>
            {status === "sending" ? "Отправка…" : "Отправить заявку"}
          </Button>
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
      </form>
    </section>
  );
}
