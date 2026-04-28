"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

const CONTACT_OPTIONS = [
  { value: "telegram", label: "Telegram" },
  { value: "whatsapp", label: "WhatsApp" },
  { value: "phone", label: "Звонок по телефону" },
  { value: "email", label: "Электронная почта" },
] as const;

export function OrderLeadForm() {
  const [fullName, setFullName] = useState("");
  const [contactMethod, setContactMethod] = useState<string>(CONTACT_OPTIONS[0].value);
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState<"idle" | "sending" | "ok" | "err">("idle");
  const [errText, setErrText] = useState("");

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus("sending");
    setErrText("");
    const label = CONTACT_OPTIONS.find((o) => o.value === contactMethod)?.label ?? contactMethod;
    try {
      const res = await fetch("/api/lead", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          full_name: fullName.trim(),
          contact_method: label,
          message: message.trim(),
        }),
      });
      if (!res.ok) {
        let detail = "";
        try {
          const j = (await res.json()) as { detail?: unknown };
          if (typeof j.detail === "string") detail = j.detail;
          else if (Array.isArray(j.detail)) detail = j.detail.map((x) => String(x)).join(" ");
        } catch {
          /* ignore */
        }
        throw new Error(detail || `Ошибка ${res.status}`);
      }
      setStatus("ok");
      setFullName("");
      setMessage("");
    } catch (err) {
      setStatus("err");
      setErrText(err instanceof Error ? err.message : "Не удалось отправить");
    }
  }

  return (
    <section
      className="mt-10 rounded-2xl border border-border/60 bg-card/80 p-6 shadow-sm ring-1 ring-black/[0.04] dark:ring-white/[0.06] sm:p-8"
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
            maxLength={200}
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="Иванов Иван Иванович"
            className="rounded-2xl"
          />
        </div>

        <div className="grid gap-2">
          <Label htmlFor="lead-contact">Предпочтительный способ связи</Label>
          <select
            id="lead-contact"
            name="contact_method"
            value={contactMethod}
            onChange={(e) => setContactMethod(e.target.value)}
            className={cn(
              "h-11 w-full min-w-0 rounded-2xl border border-transparent bg-input/50 px-3 text-base outline-none transition-[color,box-shadow,background-color]",
              "focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30 md:text-sm",
            )}
          >
            {CONTACT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>

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
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Опишите, какой автомобиль интересует (марка, год, бюджет), с какого рынка (Корея / Китай) или вставьте ссылку на объявление."
            className={cn(
              "w-full min-w-0 resize-y rounded-2xl border border-transparent bg-input/50 px-3 py-2.5 text-base outline-none transition-[color,box-shadow,background-color]",
              "placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30 md:text-sm",
            )}
          />
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <Button type="submit" size="lg" className="rounded-2xl" disabled={status === "sending"}>
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
