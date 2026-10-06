import type { Meta, StoryObj } from "@storybook/react";
import { CatalogQuickBuyDialog } from "@/components/catalog/CatalogQuickBuyDialog";
import { LocaleProvider } from "@/components/LocaleProvider";

const meta = {
  title: "Catalog/QuickBuyDialog",
  component: CatalogQuickBuyDialog,
  tags: ["autodocs"],
  decorators: [
    (Story) => (
      <LocaleProvider initialLocale="ru">
        <div className="p-6">
          <Story />
        </div>
      </LocaleProvider>
    ),
  ],
} satisfies Meta<typeof CatalogQuickBuyDialog>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    carId: "story-bmw-320",
    carTitle: "BMW 320i xDrive",
  },
};

export const CarPageCta: Story = {
  args: {
    carId: "story-bmw-320",
    carTitle: "BMW 320i xDrive",
    triggerLabel: "Купить автомобиль",
    triggerSize: "default",
    triggerVariant: "default",
    triggerClassName: "w-full max-w-xs text-sm font-semibold shadow-sm",
  },
};
