import type { Meta, StoryObj } from "@storybook/react";
import { LeadPdAgreeField } from "@/components/leads/LeadPdAgreeField";
import { LocaleProvider } from "@/components/LocaleProvider";
import { useState } from "react";

const meta = {
  title: "Leads/PdAgreeField",
  component: LeadPdAgreeField,
  tags: ["autodocs"],
  decorators: [
    (Story) => (
      <LocaleProvider initialLocale="ru">
        <div className="max-w-md p-6">
          <Story />
        </div>
      </LocaleProvider>
    ),
  ],
} satisfies Meta<typeof LeadPdAgreeField>;

export default meta;
type Story = StoryObj<typeof meta>;

function Controlled(props: { variant: "quickBuy" | "buy" }) {
  const [checked, setChecked] = useState(false);
  return <LeadPdAgreeField checked={checked} onCheckedChange={setChecked} variant={props.variant} />;
}

export const QuickBuy: Story = {
  args: { checked: false, onCheckedChange: () => {}, variant: "quickBuy" },
  render: () => <Controlled variant="quickBuy" />,
};

export const BuyPage: Story = {
  args: { checked: false, onCheckedChange: () => {}, variant: "buy" },
  render: () => <Controlled variant="buy" />,
};
