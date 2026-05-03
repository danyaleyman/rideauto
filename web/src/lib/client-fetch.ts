"use client";

/** Обёртки fetch для критичных клиентских запросов: таймаут, один повтор, понятные ошибки. */

const DEFAULT_TIMEOUT_MS = 25_000;
const RETRY_DELAY_MS = 450;

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

function isTimeoutError(e: unknown): boolean {
  return e instanceof DOMException && e.name === "TimeoutError";
}

export function humanizeHttpError(status: number, statusText: string): string {
  switch (status) {
    case 400:
      return "Некорректный запрос (400).";
    case 401:
      return "Требуется авторизация (401).";
    case 403:
      return "Доступ запрещён (403).";
    case 404:
      return "Данные не найдены (404).";
    case 408:
    case 504:
      return "Превышено время ожидания ответа сервера.";
    case 429:
      return "Слишком много запросов. Подождите немного и попробуйте снова.";
    case 502:
    case 503:
      return "Сервер временно недоступен. Попробуйте ещё раз.";
    default:
      return `Ошибка сервера ${status}${statusText ? ` (${statusText})` : ""}.`;
  }
}

function humanizeThrownError(e: unknown, fallback: string): string {
  if (isTimeoutError(e)) {
    return "Превышено время ожидания. Проверьте сеть и попробуйте снова.";
  }
  if (e instanceof TypeError) {
    return "Не удалось связаться с сервером. Проверьте подключение к сети.";
  }
  if (e instanceof Error && e.message) return e.message;
  return fallback;
}

function shouldRetryHttp(status: number): boolean {
  return status === 502 || status === 503 || status === 504 || status === 429;
}

export type FetchJsonWithRetryOptions = {
  signal?: AbortSignal;
  timeoutMs?: number;
  retries?: number;
};

export async function fetchJsonWithRetry<T>(url: string, options?: FetchJsonWithRetryOptions): Promise<T> {
  const timeoutMs = options?.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const retries = options?.retries ?? 1;
  const outer = options?.signal;
  let lastErr: unknown;

  for (let attempt = 0; attempt <= retries; attempt++) {
    const attemptController = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    const onOuterAbort = () => {
      if (timer !== undefined) clearTimeout(timer);
      attemptController.abort(outer?.reason);
    };

    try {
      timer = setTimeout(() => {
        attemptController.abort(new DOMException("Превышено время ожидания ответа", "TimeoutError"));
      }, timeoutMs);

      if (outer) {
        if (outer.aborted) {
          if (timer !== undefined) clearTimeout(timer);
          throw new DOMException("Запрос отменён", "AbortError");
        }
        outer.addEventListener("abort", onOuterAbort, { once: true });
      }

      const traceId =
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `wra-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;

      const res = await fetch(url, {
        cache: "no-store",
        headers: {
          Accept: "application/json",
          "X-Client-Trace-Id": traceId,
        },
        signal: attemptController.signal,
      });

      if (timer !== undefined) clearTimeout(timer);
      timer = undefined;
      if (outer) outer.removeEventListener("abort", onOuterAbort);

      if (!res.ok) {
        const msg = humanizeHttpError(res.status, res.statusText);
        if (attempt < retries && shouldRetryHttp(res.status)) {
          lastErr = new Error(msg);
          await sleep(RETRY_DELAY_MS);
          continue;
        }
        throw new Error(msg);
      }
      return res.json() as Promise<T>;
    } catch (e) {
      if (timer !== undefined) clearTimeout(timer);
      if (outer) outer.removeEventListener("abort", onOuterAbort);

      if (outer?.aborted) {
        throw e instanceof Error ? e : new DOMException("Запрос отменён", "AbortError");
      }

      lastErr = e;
      const retriableNetwork =
        e instanceof TypeError || isTimeoutError(e) || (e instanceof DOMException && e.name === "TimeoutError");
      if (attempt < retries && retriableNetwork) {
        await sleep(RETRY_DELAY_MS);
        continue;
      }
      throw new Error(humanizeThrownError(e, "Не удалось загрузить данные"));
    }
  }

  throw new Error(humanizeThrownError(lastErr, "Не удалось загрузить данные"));
}
