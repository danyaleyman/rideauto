"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { LeadContactMethodField } from "@/components/buy/LeadContactMethodField";
import { LeadPdAgreeField } from "@/components/leads/LeadPdAgreeField";
import { leadContactMethodLabel, type LeadContactMethodValue } from "@/lib/lead-contact-options";
import { submitLeadRequest } from "@/lib/lead-client";
import { LEAD_MESSAGE_MIN_LEN, validateLeadFullName, validateLeadPhone } from "@/lib/lead-form-validation";
import { useLocaleContext } from "@/components/LocaleProvider";

function contactValueLabel(method: LeadContactMethodValue, t: (path: string) => string): string {
  switch (method) {
    case "telegram":
      return t("buy.contactValueTelegram");
    case "whatsapp":
      return t("buy.contactValueWhatsapp");
    case "phone":
      return t("buy.contactValuePhone");
    case "email":
      return t("buy.contactValueEmail");
  }
}

function contactValuePlaceholder(method: LeadContactMethodValue, t: (path: string) => string): string {
  switch (method) {
    case "telegram":
      return t("buy.contactPlaceholderTelegram");
    case "whatsapp":
    case "phone":
      return t("buy.contactPlaceholderPhone");
    case "email":
      return t("buy.contactPlaceholderEmail");
  }
}

function validateContactValue(
  method: LeadContactMethodValue,
  value: string,
  t: (path: string) => string,
): { ok: true; normalized: string } | { ok: false; message: string } {
  const v = value.trim();
  if (!v) {
    return { ok: false, message: t("buy.contactRequired") };
  }
  if (method === "phone" || method === "whatsapp") {
    const res = validateLeadPhone(v);
    if (!res.ok) return res;
    return { ok: true, normalized: `+${res.digits}` };
  }
  if (method === "email") {
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)) {
      return { ok: false, message: t("buy.contactEmailInvalid") };
    }
    return { ok: true, normalized: v };
  }
  const isHandle = /^@[a-z0-9_]{3,32}$/i.test(v);
  const isLink = /^(https?:\/\/)?(t\.me|telegram\.me)\/[a-z0-9_]{3,}/i.test(v);
  if (!isHandle && !isLink) {
    return { ok: false, message: t("buy.contactTelegramInvalid") };
  }
  return { ok: true, normalized: v };
}

export function OrderLeadForm() {
  const { t } = useLocaleContext();
  const [fullName, setFullName] = useState("");
  const [contactMethod, setContactMethod] = useState<LeadContactMethodValue>("telegram");
  const [contactValue, setContactValue] = useState("");
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState<"idle" | "sending" | "ok" | "err">("idle");
  const [errText, setErrText] = useState("");
  const [fullNameError, setFullNameError] = useState("");
  const [contactValueError, setContactValueError] = useState("");
  const [messageError, setMessageError] = useState("");
  const [pdAgree, setPdAgree] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErrText("");
    setFullNameError("");
    setContactValueError("");
    setMessageError("");

    const nameCheck = validateLeadFullName(fullName);
    if (!nameCheck.ok) {
      setFullNameError(nameCheck.message);
      return;
    }
    const contactCheck = validateContactValue(contactMethod, contactValue, t);
    if (!contactCheck.ok) {
      setContactValueError(contactCheck.message);
      return;
    }
    if (message.trim().length < LEAD_MESSAGE_MIN_LEN) {
      setMessageError(t("buy.messageTooShort", { min: LEAD_MESSAGE_MIN_LEN }));
      return;
    }

    setStatus("sending");
    const result = await submitLeadRequest({
      full_name: fullName.trim(),
      // Значение контакта уходит в contact_method — бэкенд печатает его в «Предпочтительная связь».
      contact_method: `${leadContactMethodLabel(contactMethod)}: ${contactCheck.normalized}`,
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
    setContactValue("");
    setMessage("");
  }

  return (
    <section
      id="order-lead"
      className="mt-10 scroll-mt-24 rounded-xl border border-border bg-card p-6 sm:p-8"
      aria-labelledby="order-lead-heading"
    >
      <h2 id="order-lead-heading" className="text-xl font-semibold tracking-tight text-foreground">
        {t("buy.formTitle")}
      </h2>
      <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">{t("buy.formHint")}</p>

      <form onSubmit={onSubmit} className="mt-6 grid max-w-xl gap-5">
        <div className="grid gap-2">
          <Label htmlFor="lead-full-name">{t("buy.fullName")}</Label>
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
            placeholder={t("buy.namePlaceholder")}
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
          <Label htmlFor="lead-contact-value">{contactValueLabel(contactMethod, t)}</Label>
          <Input
            id="lead-contact-value"
            name="contact_value"
            required
            value={contactValue}
            onChange={(e) => {
              setContactValue(e.target.value);
              if (contactValueError) setContactValueError("");
            }}
            placeholder={contactValuePlaceholder(contactMethod, t)}
            type={contactMethod === "email" ? "email" : contactMethod === "phone" || contactMethod === "whatsapp" ? "tel" : "text"}
            autoComplete={contactMethod === "email" ? "email" : contactMethod === "phone" || contactMethod === "whatsapp" ? "tel" : "off"}
            inputMode={contactMethod === "email" ? "email" : contactMethod === "phone" || contactMethod === "whatsapp" ? "tel" : "text"}
            className={cn("rounded-2xl", contactValueError && "border-destructive focus-visible:ring-destructive/30")}
            aria-invalid={Boolean(contactValueError)}
            aria-describedby={contactValueError ? "lead-contact-value-error" : undefined}
          />
          {contactValueError ? (
            <p id="lead-contact-value-error" className="text-sm text-destructive" role="alert">
              {contactValueError}
            </p>
          ) : null}
        </div>

        <div className="grid gap-2">
          <Label htmlFor="lead-message">{t("buy.message")}</Label>
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
            placeholder={t("buy.messagePlaceholder")}
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

        <LeadPdAgreeField checked={pdAgree} onCheckedChange={setPdAgree} variant="buy" />

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <Button type="submit" size="lg" className="rounded-2xl" disabled={status === "sending" || !pdAgree}>
            {status === "sending" ? t("buy.sending") : t("buy.submit")}
          </Button>
          {status === "ok" ? (
            <p className="text-sm font-medium text-emerald-700 dark:text-emerald-400">{t("buy.success")}</p>
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
