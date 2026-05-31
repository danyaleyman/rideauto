/**
 * Реэкспорт сгенерированных типов OpenAPI (`npm run generate:api-types`).
 * Постепенно сводите ручные типы из `types.ts` с `components["schemas"]` из openapi.
 */
export type { components, operations, paths } from "@/lib/generated/openapi";
export { getOpenApiClient, openApiFetchCatalog, openApiFetchCatalogSearchAlias } from "@/lib/openapi-fetch-client";
