import { expect, test } from "../baserowTest";
import { TableRowContextMenuPage } from "../../pages/database/table/tableRowContextMenu";
import { TextCellPage, NumberCellPage } from "../../pages/database/table/cellPage.ts";
import { createUser } from "../../fixtures/user";
import { createRows, updateRows, deleteRows } from "../../fixtures/database/rows";
import { createField, updateField, deleteField } from "../../fixtures/database/field"
import { createWorkspaceInvitation, acceptWorkspaceInvitation } from "../../fixtures/workspace"
import { baserowConfig } from "../../playwright.config.ts"
import { FieldContextFormPage } from "../../pages/database/table/fieldContextForm.ts";
import { FieldContextMenuPage } from "../../pages/database/table/fieldContextMenu.ts";
import { TableHeaderPage } from "../../pages/database/table/tableHeader.ts";
import { FiltersPanelRowPage, FiltersPanelPage } from "../../pages/database/table/filtersPanel.ts";

test.describe("Grid view tests", () => {
  test("User can create, update, and delete a single row", async ({
    page, tablePage,
  }) => {
    await tablePage.addNewRow();

    await page.waitForTimeout(1000)
    await expect(tablePage.rows(), 'A new row was added').toHaveCount(3);

    const [newRowFieldIndex, newRowRowIndex] = [1, 2];
    const textCell = new TextCellPage(page, tablePage.getCell(newRowFieldIndex, newRowRowIndex));
    await textCell.fill('New name');

    const cellValue = await textCell.getValue();
    expect(cellValue, 'The cell in the new row was updated').toBe('New name');

    await tablePage.openRowContextMenu(newRowRowIndex);
    const rowContextMenu = new TableRowContextMenuPage(page);
    await rowContextMenu.deleteRow();

    await page.waitForTimeout(1000)
    await expect(tablePage.rows(), 'The added row was deleted').toHaveCount(2);
  });

  test("User can create, update, and delete fields", async ({
    page, tablePage
  }) => {
    await tablePage.openNewFieldContextForm();
    const newFieldContextForm = new FieldContextFormPage(page);
    await newFieldContextForm.selectFieldType('Single line text')
    await newFieldContextForm.fillName('My new field')
    await newFieldContextForm.fillDefaultText('Default value')
    await newFieldContextForm.create()

    const [fieldIndex, rowIndex] = [4, 0]
    const textCell = new TextCellPage(page, tablePage.getCell(fieldIndex, rowIndex));
    const cellValue = await textCell.getValue();
    expect(cellValue, 'The field was created with default value').toBe('Default value');

    await tablePage.openFieldContextMenu(fieldIndex)
    const fieldContextMenu = new FieldContextMenuPage(page)
    await fieldContextMenu.edit()

    const editFieldContextForm = new FieldContextFormPage(page);
    await editFieldContextForm.focusFieldType()
    await editFieldContextForm.selectFieldType('Autonumber')
    await editFieldContextForm.fillName('Changed field name')
    await editFieldContextForm.save()

    const autoNumberCell = new NumberCellPage(page, tablePage.getCell(fieldIndex, rowIndex))
    const autoNumbercellValue = await autoNumberCell.getValue();
    expect(autoNumbercellValue, 'The field values were changed to autonumbers').toBe('1')

    await tablePage.openFieldContextMenu(fieldIndex)
    await fieldContextMenu.delete()

    await page.waitForTimeout(1000)
    expect(tablePage.fields(), 'Field was deleted').toHaveCount(3)
  })

  test("User can hide and show fields", async ({
    page, tablePage
  }) => {
    await tablePage.openFieldContextMenu(2)
    const fieldContextMenu = new FieldContextMenuPage(page)
    await fieldContextMenu.hide()

    expect(tablePage.fields(), 'Field was hidden').toHaveCount(2)

    // Show again
    await page.locator('a').filter({ hasText: 'hidden field' }).click();
    await page.locator('div').filter({ hasText: 'Notes' }).nth(2).click();

    expect(tablePage.fields(), 'Field is not hidden anymore').toHaveCount(3)
  })

  test("User can create and delete filters", async ({
    page, tablePage
  }) => {
      const headerPage = new TableHeaderPage(page)
      await headerPage.toggleFiltersPanel()

      const filtersPanelPage = new FiltersPanelPage(page)
      filtersPanelPage.addFilter()

      // Set 'is' filter for 'Active' field
      await page.locator('a').filter({ hasText: 'Name' }).first().click();
      await page.waitForTimeout(1000);
      await page.locator('a').filter({ hasText: 'Active' }).click();
      await page.waitForTimeout(1000);
      const firstFilterPage = new FiltersPanelRowPage(page, filtersPanelPage.getFilterRow(0))
      await firstFilterPage.filterRow.locator('.checkbox__button').click()
      await headerPage.toggleFiltersPanel()

      await expect(tablePage.rows(), 'Filter is applied').toHaveCount(0);

      // Remove filter
      await headerPage.toggleFiltersPanel()
      await firstFilterPage.delete()

      await page.waitForTimeout(1000)
      await expect(tablePage.rows(), 'Filter successfully removed').toHaveCount(2);
  })
});

test.describe("Grid view collaboration tests", () => {
  test("User can see created, updated and deleted rows", async ({
    page, tablePage,
  }) => {
    const baseUrl = baserowConfig.PUBLIC_WEB_FRONTEND_URL;
    const collaborator = await createUser();
    const invitation = await createWorkspaceInvitation(tablePage.user, tablePage.workspace, collaborator.email, "ADMIN", "", baseUrl);
    await acceptWorkspaceInvitation(collaborator, invitation);

    const createdRows = await createRows(collaborator, tablePage.table, [{}]);

    await page.waitForTimeout(1000)
    await expect(tablePage.rows(), 'A new row was added').toHaveCount(3);

    await updateRows(collaborator, tablePage.table, [{ 'id': createdRows[0].id, "Name": "New name" }]);

    const [newRowFieldIndex, newRowRowIndex] = [1, 2];
    const textCell = new TextCellPage(page, tablePage.getCell(newRowFieldIndex, newRowRowIndex));
    const cellValue = await textCell.getValue();
    expect(cellValue, 'The cell in the new row was updated').toBe('New name');

    await deleteRows(collaborator, tablePage.table, [createdRows[0].id]);

    await page.waitForTimeout(1000)
    await expect(tablePage.rows(), 'The added row was deleted').toHaveCount(2);
  });

  test("User can see created, updated, and deleted fields", async ({
    page, tablePage
  }) => {
    const baseUrl = baserowConfig.PUBLIC_WEB_FRONTEND_URL;
    const collaborator = await createUser();
    const invitation = await createWorkspaceInvitation(tablePage.user, tablePage.workspace, collaborator.email, "ADMIN", "", baseUrl);
    await acceptWorkspaceInvitation(collaborator, invitation);

    const newField = await createField(collaborator, "New field", "text", { text_default: "Default value" }, tablePage.table)

    expect(tablePage.fields(), 'Field was deleted').toHaveCount(4)

    const [fieldIndex, rowIndex] = [4, 0]
    const textCell = new TextCellPage(page, tablePage.getCell(fieldIndex, rowIndex));
    const cellValue = await textCell.getValue();
    expect(cellValue, 'The field was created with default value').toBe('Default value');

    await updateField(collaborator, "New field updated", "autonumber", {}, newField)

    const autoNumberCell = new NumberCellPage(page, tablePage.getCell(fieldIndex, rowIndex))
    const autoNumbercellValue = await autoNumberCell.getValue();
    expect(autoNumbercellValue, 'The field values were changed to autonumbers').toBe('1')

    await deleteField(collaborator, newField)

    expect(tablePage.fields(), 'Field was deleted').toHaveCount(3)
  })
});

