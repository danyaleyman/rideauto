import type { Meta, StoryObj } from "@storybook/react";
import { CatalogListingCard } from "@/components/catalog/CatalogListingCard";
import { LocaleProvider } from "@/components/LocaleProvider";
import { createStoryCatalogMock, storySlimCar } from "@/stories/story-fixtures";

const catalog = createStoryCatalogMock();
const preview = storySlimCar.data?.images?.length
  ? (storySlimCar.data.images as string[])
  : ["/assets/korea-fallback-image.png"];

const meta = {
  title: "Catalog/ListingCard",
  component: CatalogListingCard,
  tags: ["autodocs"],
  parameters: { layout: "padded" },
  decorators: [
    (Story) => (
      <LocaleProvider initialLocale="ru">
        <ul className="mx-auto max-w-3xl list-none p-4">
          <Story />
        </ul>
      </LocaleProvider>
    ),
  ],
} satisfies Meta<typeof CatalogListingCard>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Available: Story = {
  args: {
    catalog,
    car: storySlimCar,
    idx: 0,
    preview,
  },
};

export const Sold: Story = {
  args: {
    catalog,
    car: { ...storySlimCar, id: "story-sold", encar_listing_sold: true },
    idx: 1,
    preview,
  },
};

export const Compact: Story = {
  args: {
    catalog: createStoryCatalogMock({ catalogDensity: "compact" }),
    car: storySlimCar,
    idx: 0,
    preview,
  },
};
