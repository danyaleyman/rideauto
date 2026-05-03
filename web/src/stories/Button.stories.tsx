import type { Meta, StoryObj } from "@storybook/nextjs";
import { Button } from "@/components/ui/button";

const meta = {
  title: "UI/Button",
  component: Button,
  tags: ["autodocs"],
} satisfies Meta<typeof Button>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Primary: Story = {
  args: {
    children: "Открыть каталог",
    size: "lg",
    className: "rounded-xl",
  },
};

export const Outline: Story = {
  args: {
    children: "Как купить",
    variant: "outline",
    size: "lg",
    className: "rounded-xl",
  },
};
