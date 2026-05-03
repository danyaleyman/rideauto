import type { Meta, StoryObj } from "@storybook/react";
import { Skeleton } from "@/components/ui/skeleton";

const meta = {
  title: "UI/Skeleton",
  component: Skeleton,
  tags: ["autodocs"],
} satisfies Meta<typeof Skeleton>;

export default meta;
type Story = StoryObj<typeof meta>;

export const CardRow: Story = {
  render: () => (
    <div className="flex max-w-md flex-col gap-3 p-4">
      <Skeleton className="h-40 w-full rounded-xl" />
      <Skeleton className="h-6 w-3/4 rounded-lg" />
      <Skeleton className="h-6 w-1/2 rounded-lg" />
    </div>
  ),
};
