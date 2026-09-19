import { expect, test } from "@playwright/test";

test("busca produtos e abre comparação", async ({ page }) => {
  await page.goto("/");

  const searchInput = page.getByRole("searchbox", {
    name: "Buscar produtos",
  });

  await searchInput.fill("notebook");

  await page.getByRole("button", { name: "Buscar" }).click();

  await expect(page).toHaveURL(/q=notebook/);

  const compareCheckboxes = page.getByRole("checkbox", {
    name: "Comparar este produto",
  });

  await expect(compareCheckboxes.first()).toBeVisible();

  const count = await compareCheckboxes.count();

  expect(count).toBeGreaterThanOrEqual(2);

  await compareCheckboxes.nth(0).check();
  await compareCheckboxes.nth(1).check();

  const compareButton = page.getByRole("button", {
    name: "Comparar produtos",
  });

  await expect(compareButton).toBeEnabled();

  await compareButton.click();

  await expect(page).toHaveURL(/\/compare\?ids=/);

  await expect(
    page.getByText("Compare preços e especificações dos produtos selecionados.")
  ).toBeVisible();
});
