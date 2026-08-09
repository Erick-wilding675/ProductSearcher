import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { ComparisonTable } from "./ComparisonTable";
import type { CompareResult } from "@/lib/api";

const meta: Meta<typeof ComparisonTable> = {
  title: "Components/ComparisonTable",
  component: ComparisonTable,
};

export default meta;

type Story = StoryObj<typeof ComparisonTable>;

const comparison: CompareResult = {
  category: "notebooks",

  products: [
    {
      id: "1",
      name: "Notebook Lenovo IdeaPad",
      min_price: "4500.00",
    },
    {
      id: "2",
      name: "Notebook Acer Aspire",
      min_price: "3999.00",
    },
    {
      id: "3",
      name: "Notebook Dell Inspiron",
      min_price: "4800.00",
    },
  ],

  best_value_id: "2",

  attributes: [
    {
      key: "ram_gb",
      values: [8, 16, 16],
      differ: true,
    },
    {
      key: "storage_type",
      values: ["SSD", "SSD", "SSD"],
      differ: false,
    },
    {
      key: "anc",
      values: [false, true, true],
      differ: true,
    },
  ],
};

export const Default: Story = {
  args: {
    comparison,
  },
};

export const EqualPrice: Story = {
  args: {
    comparison: {
      ...comparison,
      products: comparison.products.map((product) => ({
        ...product,
        min_price: "3999.00",
      })),
      best_value_id: null,
    },
  },
};

export const MissingPrice: Story = {
  args: {
    comparison: {
      ...comparison,
      products: comparison.products.map((product) => ({
        ...product,
        min_price: null,
      })),
      best_value_id: null,
    },
  },
};

export const DifferentSpecs: Story = {
  args: {
    comparison: {
      ...comparison,
      attributes: [
        {
          key: "ram_gb",
          values: [8, 16, 32],
          differ: true,
        },
        {
          key: "storage_type",
          values: ["SSD", "SSD", "HDD"],
          differ: true,
        },
        {
          key: "anc",
          values: [false, true, true],
          differ: true,
        },
      ],
    },
  },
};
