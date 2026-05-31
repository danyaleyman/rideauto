/** Текст плейсхолдера превью в карточке каталога (тестируемая логика без React). */
export function catalogCardImagePlaceholder(hasSourceUrls: boolean): string {
  return hasSourceUrls ? "Загрузка фото…" : "Нет фото";
}
