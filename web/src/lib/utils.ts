import { clsx, type ClassValue } from "clsx"
import { extendTailwindMerge } from "tailwind-merge"

/**
 * Кастомные типографические утилиты из globals.css (text-caption, text-title-sm, …)
 * должны считаться font-size, а не цветом текста — иначе twMerge вырезает
 * `text-primary-foreground` и т.п. при их совместном использовании.
 */
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": ["text-caption", "text-title-sm", "text-price", "text-display-sm"],
    },
  },
})

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
