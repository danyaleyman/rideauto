import { useState } from "react";
import type { Meta, StoryObj } from "@storybook/react";
import { SegmentedControl, SegmentedControlPill } from "@/components/ui/segmented-control";

const meta = {
  title: "UI/SegmentedControl",
  tags: ["autodocs"],
} satisfies Meta;

export default meta;

export const Tabs: StoryObj = {
  render: function TabsStory() {
    const [value, setValue] = useState<"a" | "b">("a");
    return (
      <SegmentedControl
        value={value}
        onChange={setValue}
        aria-label="Демо табы"
        items={[
          { value: "a", label: "Вариант A" },
          { value: "b", label: "Вариант B" },
        ]}
      />
    );
  },
};

export const PillMarket: StoryObj = {
  render: function PillStory() {
    const [value, setValue] = useState<"korea" | "china">("korea");
    return (
      <SegmentedControlPill
        value={value}
        onChange={setValue}
        aria-label="Рынок"
        items={[
          { value: "korea", label: "Корея" },
          { value: "china", label: "Китай" },
        ]}
      />
    );
  },
};
