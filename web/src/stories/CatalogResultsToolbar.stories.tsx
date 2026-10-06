import type { Meta, StoryObj } from "@storybook/react";
import { CatalogResultsToolbar } from "@/components/catalog/CatalogResultsToolbar";
import { LocaleProvider } from "@/components/LocaleProvider";
import { createStoryCatalogMock } from "@/stories/story-fixtures";
import { useState } from "react";
import type { CatalogSearchController } from "@/hooks/use-catalog-search-state";

const meta = {
  title: "Catalog/ResultsToolbar",
  component: CatalogResultsToolbar,
  tags: ["autodocs"],
  decorators: [
    (Story) => (
      <LocaleProvider initialLocale="ru">
        <div className="max-w-4xl p-4">
          <Story />
        </div>
      </LocaleProvider>
    ),
  ],
} satisfies Meta<typeof CatalogResultsToolbar>;

export default meta;
type Story = StoryObj<typeof meta>;

function InteractiveToolbar() {
  const [qDraft, setQDraft] = useState("BMW");
  const catalog = createStoryCatalogMock({
    qDraft,
    setQDraft,
    search: {
      result: [],
      meta: { total: 1284, limit: 24, per_page: 24, pages: 54, offset: 0 },
    },
  }) as CatalogSearchController;
  return <CatalogResultsToolbar catalog={catalog} />;
}

export const Default: Story = {
  args: { catalog: createStoryCatalogMock() },
};

export const WithQuery: Story = {
  args: { catalog: createStoryCatalogMock({ qDraft: "BMW" }) },
  render: () => <InteractiveToolbar />,
};
