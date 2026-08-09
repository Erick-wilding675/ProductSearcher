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

    categories: [
      { value: "notebooks", label: "Notebooks" },
      { value: "headphones", label: "Fones de ouvido" },
    ],

    brands: [
      { value: "lenovo", label: "Lenovo" },
      { value: "acer", label: "Acer" },
      { value: "dell", label: "Dell" },
      { value: "asus", label: "Asus" },
      { value: "jbl", label: "JBL" },
    ],

    onCategoryChange: () => {},
    onPriceMaxChange: () => {},
    onBrandChange: () => {},
    onApply: () => {},
    onClear: () => {},
  },
};
