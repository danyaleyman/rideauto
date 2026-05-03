/** Общие правила для форм заявки (страница «Купить» и быстрый заказ из каталога). */

export const LEAD_NAME_MIN_LEN = 2;
export const LEAD_NAME_MAX_LEN = 100;
export const LEAD_MESSAGE_MIN_LEN = 10;

const NAME_PATTERN = /^[\p{L}\s\-'.]+$/u;

export function normalizeRussianMobileDigits(input: string): string {
  let d = input.replace(/\D/g, "");
  if (d.length === 10 && d.startsWith("9")) d = `7${d}`;
  if (d.length === 11 && d.startsWith("8")) d = `7${d.slice(1)}`;
  return d;
}

export function isValidRussianMobileDigits(digits: string): boolean {
  return /^7\d{10}$/.test(digits);
}

export function validateLeadFullName(name: string): { ok: true } | { ok: false; message: string } {
  const t = name.trim();
  if (t.length < LEAD_NAME_MIN_LEN) {
    return { ok: false, message: `Укажите имя не короче ${LEAD_NAME_MIN_LEN} символов` };
  }
  if (t.length > LEAD_NAME_MAX_LEN) {
    return { ok: false, message: `Не больше ${LEAD_NAME_MAX_LEN} символов` };
  }
  if (!NAME_PATTERN.test(t)) {
    return {
      ok: false,
      message: "Допустимы буквы (в т.ч. латиница), пробел, дефис и апостроф",
    };
  }
  return { ok: true };
}

export function validateLeadPhone(input: string): { ok: true; digits: string } | { ok: false; message: string } {
  const digits = normalizeRussianMobileDigits(input);
  if (!isValidRussianMobileDigits(digits)) {
    return {
      ok: false,
      message: "Введите мобильный номер РФ: 11 цифр, начинается с 7 или 8",
    };
  }
  return { ok: true, digits };
}

export async function readLeadErrorMessage(res: Response): Promise<string> {
  let detail = "";
  try {
    const j = (await res.json()) as { detail?: unknown };
    if (typeof j.detail === "string") detail = j.detail;
    else if (Array.isArray(j.detail)) detail = j.detail.map((x) => String(x)).join(" ");
  } catch {
    /* ignore */
  }
  return detail || `Ошибка ${res.status}`;
}
