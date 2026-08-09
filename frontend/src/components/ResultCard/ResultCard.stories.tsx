import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { ResultCard } from "./ResultCard";
import type { SearchResultItem } from "@/lib/api";

const meta: Meta<typeof ResultCard> = {
  title: "Components/ResultCard",
  component: ResultCard,
};

export default meta;

type Story = StoryObj<typeof ResultCard>;

const product: SearchResultItem = {
  id: "1",
  slug: "notebook-lenovo-ideapad",
  name: "Notebook Lenovo IdeaPad",
  category: "notebooks",
  brand: "Lenovo",
  min_price: "3999.00",

  specs: {
    ram_gb: 16,
    storage_type: "SSD",
    anc: true,
  },

  score: 0.84,

  factors: {
    relevance: {
      score: 1,
      applicable: true,
    },
    price: {
      score: 0.78,
      applicable: true,
    },
    attributes: {
      score: 0,
      applicable: false,
    },
  },
};

export const Default: Story = {
  args: {
    product,
    selectedForComparison: false,
    onCompareChange: () => {},
  },
};

export const Selected: Story = {
  args: {
    product,
    selectedForComparison: true,
    onCompareChange: () => {},
  },
};

export const WithoutSpecs: Story = {
  args: {
    product: {
      ...product,
      specs: {},
    },
    selectedForComparison: false,
    onCompareChange: () => {},
  },
};

export const WithoutPrice: Story = {
  args: {
    product: {
      ...product,
      min_price: null,
    },
    selectedForComparison: false,
    onCompareChange: () => {},
  },
};
