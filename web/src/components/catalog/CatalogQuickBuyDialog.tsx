"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getCarPageAbsoluteUrl } from "@/lib/car-url";

type Props = {
  carId: string;
  carTitle: string;
  triggerLabel?: string;
  triggerClassName?: string;
  triggerSize?: "sm" | "default" | "lg";
};

const NAME_RE = /^[А-Яа-яЁё\s-]{1,10}$/;
const PHONE_RE = /^[78]\d{10}$/;

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

  async function submit() {
    const fullName = name.trim();
    const contact = phone.trim();
    if (!NAME_RE.test(fullName) || !PHONE_RE.test(contact)) return;
    setStatus("sending");
    setErrText("");
    try {
      const link = getCarPageAbsoluteUrl(carId);
      const message = [
        "Заявка на покупку из каталога",
        `Автомобиль: ${carTitle}`,
        `Ссылка: ${link}`,
        "",
        `Имя клиента: ${fullName}`,
        `Контактный номер: ${contact}`,
      ].join("\n");
      const res = await fetch("/api/lead", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          full_name: fullName,
          contact_method: "Звонок по телефону",
          message,
        }),
      });
      if (!res.ok) {
        let detail = "";
        try {
          const j = (await res.json()) as { detail?: unknown };
          if (typeof j.detail === "string") detail = j.detail;
        } catch {
          // ignore
        }
        throw new Error(detail || `Ошибка ${res.status}`);
      }
      setStatus("ok");
      setName("");
      setPhone("");
    } catch (e) {
      setStatus("err");
      setErrText(e instanceof Error ? e.message : "Не удалось отправить заявку");
    }
  }

  const isValidName = NAME_RE.test(name.trim());
  const isValidPhone = PHONE_RE.test(phone.trim());

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button type="button" size={triggerSize} className={triggerClassName ?? "rounded-lg ms-auto"}>
          {triggerLabel}
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md" showCloseButton>
        <DialogHeader>
          <DialogTitle>Оставить заявку на покупку</DialogTitle>
          <DialogDescription>{carTitle}</DialogDescription>
        </DialogHeader>
        <div className="grid gap-3">
          <div className="grid gap-1.5">
            <Label htmlFor={`buy-name-${carId}`}>Имя</Label>
            <Input
              id={`buy-name-${carId}`}
              value={name}
              onChange={(e) => {
                const next = e.target.value.replace(/[^А-Яа-яЁё\s-]/g, "").slice(0, 10);
                setName(next);
              }}
              placeholder="Ваше имя"
              autoComplete="name"
              minLength={1}
              maxLength={10}
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor={`buy-phone-${carId}`}>Контактный номер</Label>
            <Input
              id={`buy-phone-${carId}`}
              value={phone}
              onChange={(e) => {
                const digits = e.target.value.replace(/\D/g, "").slice(0, 11);
                setPhone(digits);
              }}
              placeholder="+7 ..."
              autoComplete="tel"
              inputMode="numeric"
              minLength={11}
              maxLength={11}
            />
          </div>
          <Button
            type="button"
            onClick={submit}
            disabled={status === "sending" || !isValidName || !isValidPhone}
          >
            {status === "sending" ? "Отправка..." : "Отправить"}
          </Button>
          {status === "ok" ? (
            <p className="text-sm font-medium text-emerald-700 dark:text-emerald-400">
              Ваша заявка отправлена, в ближайшее время с вами свяжется менеджер.
            </p>
          ) : null}
          {status === "err" ? (
            <p className="text-sm text-destructive" role="alert">
              {errText}
            </p>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
