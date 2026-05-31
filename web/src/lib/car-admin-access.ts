/** Админ-панель карточки: только эти учётные записи после magic-link входа. */
const CAR_LISTING_ADMIN_EMAILS = new Set([
  "nikita-yudin-1998@mail.ru",
  "danyaleyman@yandex.ru",
]);

export function isCarListingAdmin(email: string | null | undefined): boolean {
  if (!email?.trim()) return false;
  return CAR_LISTING_ADMIN_EMAILS.has(email.trim().toLowerCase());
}
