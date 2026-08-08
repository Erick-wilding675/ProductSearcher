import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { FilterPanel } from "./FilterPanel";

const meta: Meta<typeof FilterPanel> = {
  title: "Components/FilterPanel",
  component: FilterPanel,
};

export default meta;

type Story = StoryObj<typeof FilterPanel>;

export const Default: Story = {
  args: {
    category: "",
    priceMax: "",
    brand: "",
    categories: ["notebooks", "headphones"],
    brands: ["Lenovo", "Acer", "Dell", "Sony"],
    onCategoryChange: () => {},
    onPriceMaxChange: () => {},
    onBrandChange: () => {},
    onClear: () => {},
  },
};