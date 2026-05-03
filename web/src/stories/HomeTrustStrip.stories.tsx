import type { Meta, StoryObj } from "@storybook/nextjs";
import { HomeTrustStrip } from "@/components/home/HomeTrustStrip";

const meta = {
  title: "Home/TrustStrip",
  component: HomeTrustStrip,
  parameters: {
    layout: "fullscreen",
  },
  decorators: [
    (Story) => (
      <div className="bg-background p-6">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof HomeTrustStrip>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {};
