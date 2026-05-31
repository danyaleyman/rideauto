import type { Meta, StoryObj } from "@storybook/react";
import { ListingChip } from "@/components/ui/listing-chip";

const meta = {
  title: "UI/ListingChip",
  component: ListingChip,
  tags: ["autodocs"],
  decorators: [
    (Story) => (
      <div className="flex flex-wrap gap-2 p-4">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof ListingChip>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Neutral: Story = {
  args: { tone: "neutral", size: "md", children: "245 000 км" },
};

export const CommerceAmber: Story = {
  args: { tone: "commerceAmber", size: "md", children: "Без таможни РФ" },
};

export const Overlay: Story = {
  args: { tone: "overlay", size: "sm", children: "2022" },
  decorators: [
    (Story) => (
      <div className="rounded-lg bg-neutral-800 p-4">
        <Story />
      </div>
    ),
  ],
};
