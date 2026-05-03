export type ThemePreference = "light" | "dark" | "system";

const STORAGE_KEY = "wra-theme";

export function normalizeThemePreference(raw: string | null): ThemePreference {
  if (raw === "light" || raw === "dark" || raw === "system") return raw;
  return "system";
}

export function readThemePreference(): ThemePreference {
  if (typeof window === "undefined") return "system";
  return normalizeThemePreference(window.localStorage.getItem(STORAGE_KEY));
}

export function writeThemePreference(pref: ThemePreference): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, pref);
}

/** Применить класс `dark` на <html> по сохранённой настройке или системной теме. */
export function applyThemePreference(pref: ThemePreference): void {
  if (typeof document === "undefined") return;
  const dark =
    pref === "dark" ||
    (pref === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", dark);
}
