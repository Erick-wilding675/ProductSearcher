import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { SearchBar } from "./SearchBar";

const meta: Meta<typeof SearchBar> = {
  title: "Components/SearchBar",
  component: SearchBar,
};

export default meta;

type Story = StoryObj<typeof SearchBar>;

export const Default: Story = {
  args: {
    value: "",
    onChange: () => {},
    onSearch: () => {},
  },
};

export const WithQuery: Story = {
  args: {
    value: "notebook gamer",
    onChange: () => {},
    onSearch: () => {},
  },
};