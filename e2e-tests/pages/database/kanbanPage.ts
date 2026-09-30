import { expect, Locator, Page } from "@playwright/test";
import { Database } from "../../fixtures/database/database";
import { Table } from "../../fixtures/database/table";
import { User } from "../../fixtures/user";
import { View } from "../../fixtures/database/view";
import { openTableAs } from "./tableNavigation";

/** Page object for the premium kanban view; stacks are addressed by option label. */
export class KanbanPage {
  constructor(
    readonly page: Page,
    private readonly user: User,
  ) {}

  async goTo(database: Database, table: Table, view: View): Promise<void> {
    await openTableAs(this.page, this.user, database, table, view);
    await expect(this.page.locator(".kanban-view__stack").first()).toBeVisible({
      timeout: 25_000,
    });
  }

  stack(option: string): Locator {
    return this.page.locator(".kanban-view__stack", {
      has: this.page.locator(".kanban-view__option", {
        hasText: new RegExp(
          `^\\s*${option.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*$`,
        ),
      }),
    });
  }

  /** The cards shown in the stack; buffer slots without a row stay hidden. */
  cards(option: string): Locator {
    return this.stack(option).locator(".kanban-view__stack-card:visible");
  }

  card(option: string, text: string): Locator {
    return this.cards(option).filter({ hasText: text });
  }

  async expectStackCount(option: string, count: number): Promise<void> {
    await expect(this.stack(option).locator(".kanban-view__count")).toHaveText(
      new RegExp(`^\\s*${count}\\s*$`),
      { timeout: 10_000 },
    );
    await expect(this.cards(option)).toHaveCount(count, { timeout: 10_000 });
  }

  /** Drags the card with real mouse events, which is what the stacks listen to. */
  async dragCardToStack(
    fromOption: string,
    text: string,
    toOption: string,
  ): Promise<void> {
    const cardBox = await this.card(fromOption, text).boundingBox();
    const targetBox = await this.stack(toOption)
      .locator(".kanban-view__stack-cards")
      .boundingBox();
    if (cardBox === null || targetBox === null) {
      throw new Error(`Expected card "${text}" and stack "${toOption}".`);
    }
    const startX = cardBox.x + cardBox.width / 2;
    const startY = cardBox.y + cardBox.height / 2;
    await this.page.mouse.move(startX, startY);
    await this.page.mouse.down();
    await this.page.mouse.move(startX + 10, startY + 10, { steps: 2 });
    await this.page.mouse.move(
      targetBox.x + targetBox.width / 2,
      targetBox.y + 30,
      { steps: 10 },
    );
    await this.page.mouse.up();
  }

  /** Opens the create row modal from the "+" at the bottom of the stack. */
  async openCreateRowModal(option: string): Promise<Locator> {
    await this.stack(option).locator(".kanban-view__stack-foot button").click();
    const modal = this.page.locator(".modal__box", {
      has: this.page.locator(".row-modal__title"),
    });
    await expect(modal).toBeVisible({ timeout: 10_000 });
    return modal;
  }
}
