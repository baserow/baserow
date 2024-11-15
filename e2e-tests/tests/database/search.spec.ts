import { expect, test } from "../baserowTest";
import { TablePage } from "../../pages/database/tablePage";
import { createUser, deleteUser, User } from "../../fixtures/user";
import { createWorkspace, Workspace } from "../../fixtures/workspace";
import { createDatabase, Database } from "../../fixtures/database/database";
import { createTable, Table } from "../../fixtures/database/table";
import {
  createField,
  deleteAllNonPrimaryFieldsFromTable,
  deleteField,
  Field,
  getFieldsForTable,
  updateField,
} from "../../fixtures/database/field";
import { updateRows } from "../../fixtures/database/rows";
import { WorkspacePage } from "../../pages/workspacePage";

let user: User;
let sharedPageTestData: SharedTestData;
let page;
let workspacePage;

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ browser }) => {
  page = await browser.newPage();

  user = await createUser();
  const workspace = await createWorkspace(user);
  workspacePage = new WorkspacePage(page, user, workspace);
  await workspacePage.authenticate();

  sharedPageTestData = await setupTestTablesAndUser(workspacePage);
});

test.afterAll(async () => {
  // We only want to bother cleaning up in a devs local env or when pointed at a real
  // server. If in CI then the first user will be the first admin and this will fail.
  // Secondly in CI we are going to delete the database anyway so no need to clean-up.
  if (!process.env.CI) {
    await deleteUser(user);
  }
  await page.close();
});

class SharedTestData {
  constructor(
    public workspace: Workspace,
    public database: Database,
    public tableA: Table,
    public tableB: Table,
    public tableC: Table
  ) {}
}

async function setupTestTablesAndUser(workspacePage): Promise<SharedTestData> {
  // const workspace = await getUsersFirstWorkspace(user);
  const database = await createDatabase(
    workspacePage.user,
    "searchTestDb",
    workspacePage.workspace
  );
  const tableA = await createTable(
    workspacePage.user,
    "searchTestTableA",
    database
  );
  await deleteAllNonPrimaryFieldsFromTable(workspacePage.user, tableA);
  const tableB = await createTable(
    workspacePage.user,
    "searchTestTableB",
    database
  );
  await deleteAllNonPrimaryFieldsFromTable(workspacePage.user, tableB);
  const tableC = await createTable(
    workspacePage.user,
    "searchTestTableB",
    database
  );
  await deleteAllNonPrimaryFieldsFromTable(workspacePage.user, tableC);
  return new SharedTestData(
    workspacePage.workspace,
    database,
    tableA,
    tableB,
    tableC
  );
}

class TestCase {
  setup: boolean;

  constructor(
    public fieldType: FieldType,
    public subFieldSetup: SubFieldSetup,
    public cellValue: string,
    public searchTerms: string[],
    public expectsCellToMatch: boolean,
    public matchRowIdColumn: boolean,
    public last: boolean
  ) {
    this.setup = false;
  }

  async doSetup(tablePage: TablePage) {
    // Input searchable value
    if (this.subFieldSetup.setCellFunc) {
      await this.subFieldSetup.setCellFunc(tablePage, this.cellValue);
    } else {
      const rowValue = { id: 1 };
      rowValue[this.subFieldSetup.field.name] = null;
      await updateRows(user, sharedPageTestData.tableA, [rowValue]);
      rowValue[this.subFieldSetup.field.name] = this.cellValue;
      await updateRows(user, sharedPageTestData.tableA, [rowValue]);
      await tablePage.waitForFirstCellNotBeBlank();
    }
    // Nothing should have changed as no search term is set
    await expect(tablePage.rows()).toHaveCount(2);
    await expect(tablePage.searchMatchingCells()).toHaveCount(0);
    this.setup = true;
  }
}

class SubFieldSetup {
  readonly testCases: TestCase[];
  setup: boolean;
  field: Field;
  otherFields: Field[];

  constructor(
    public name: string,
    public fieldType: FieldType,
    public fieldSettings: () => any,
    public otherFieldsToMakeOrUpdate: () => any[],
    public setCellFunc: Function | null,
    public testCaseInputs: TestCaseInput[]
  ) {
    this.setup = false;
    this.testCases = [];
    for (let i = 0; i < testCaseInputs.length; i++) {
      const testCaseInput = testCaseInputs[i];
      this.testCases.push(
        new TestCase(
          fieldType,
          this,
          testCaseInput.whenCellIs,
          testCaseInput.andSearchTermsAre,
          testCaseInput.expectCellMatches,
          testCaseInput.matchRowIdColumn,
          i === testCaseInputs.length - 1
        )
      );
    }
  }

  async doSetup(tablePage: TablePage) {
    await expect(tablePage.fields()).toHaveCount(1);
    // Premake the field so it always the first field in the list
    this.field = await createField(
      user,
      this.name,
      "text",
      {},
      sharedPageTestData.tableA
    );
    this.otherFields = [];
    for (const otherField of this.otherFieldsToMakeOrUpdate()) {
      if (otherField.updatePrimary) {
        const primary = await this._getPrimary(otherField);
        this.otherFields.push(
          await updateField(
            user,
            otherField.name,
            otherField.type,
            otherField.settings,
            primary
          )
        );
      } else {
        this.otherFields.push(
          await createField(
            user,
            otherField.name,
            otherField.type,
            otherField.settings,
            otherField.table
          )
        );
      }
    }
    this.field = await updateField(
      user,
      this.name,
      this.fieldType.type,
      this.fieldSettings(),
      this.field
    );
    // Double check page is as expected
    await tablePage.waitForLoadingOverlayToDisappear();
    await expect(tablePage.fields()).toHaveCount(this.expectedNumFields(), {
      timeout: 30000,
    });
    this.setup = true;
  }

  private async _getPrimary(otherField) {
    const fields = await getFieldsForTable(user, otherField.table);
    return fields.filter((f) => f.fieldSettings.primary)[0];
  }

  private expectedNumFields() {
    // Primary + Test + Other test fields
    return (
      2 +
      this.otherFields.filter(
        (f) => f.table.id === sharedPageTestData.tableA.id
      ).length
    );
  }

  async tearDown(tablePage: TablePage) {
    await deleteField(user, this.field);
    for (const otherField of this.otherFields.reverse()) {
      if (otherField.fieldSettings.primary) {
        const primary = await this._getPrimary(otherField);
        await updateField(user, primary.name, "text", {}, primary);
        const blankRows = [];
        for (let i = 1; i < 3; i++) {
          const o = {
            id: i,
          };
          o[primary.name] = null;
          blankRows.push(o);
        }
        await updateRows(user, primary.table, blankRows);
      } else {
        await deleteField(user, otherField);
      }
    }
    await expect(tablePage.fields()).toHaveCount(1);
  }
}

type TestCaseInput = {
  whenCellIs;
  andSearchTermsAre: string[];
  expectCellMatches: boolean;
  matchRowIdColumn: boolean;
};

type FieldInput = {
  type: string;
  name: string;
  settings?: Record<string, any>;
  table: Table;
};

type SubFieldSetupInput = {
  name?: string;
  testCases?: TestCaseInput[];
  fieldSettings?: Record<string, any>;
  otherFieldsToMakeOrUpdate?: () => FieldInput[];
  setCellValueFunc?: (TablePage, any) => void;
};

class FieldType {
  public readonly subFieldSetups: SubFieldSetup[];

  constructor(
    public type: string,
    public subFieldSetupInputs: SubFieldSetupInput[],
    public defaultSubFieldSetupValue: SubFieldSetupInput
  ) {
    this.subFieldSetups = subFieldSetupInputs.map(
      (i) =>
        new SubFieldSetup(
          i.name,
          this,
          () => {
            let defaultFieldSettings = defaultSubFieldSetupValue.fieldSettings;
            if (typeof defaultFieldSettings === "function") {
              defaultFieldSettings = defaultFieldSettings();
            }
            return { ...defaultFieldSettings, ...i.fieldSettings };
          },
          () => {
            let result = [];
            if (defaultSubFieldSetupValue.otherFieldsToMakeOrUpdate) {
              result = result.concat(
                defaultSubFieldSetupValue.otherFieldsToMakeOrUpdate()
              );
            }
            if (i.otherFieldsToMakeOrUpdate) {
              result = result.concat(i.otherFieldsToMakeOrUpdate());
            }
            return result;
          },
          defaultSubFieldSetupValue.setCellValueFunc || i.setCellValueFunc,
          i.testCases
        )
    );
  }
}

function matchesWithoutSelf(cell, ...searches): TestCaseInput {
  return {
    whenCellIs: cell,
    andSearchTermsAre: Array.from(new Set(searches)),
    expectCellMatches: true,
    matchRowIdColumn: false,
  };
}

function matches(cell, ...searches): TestCaseInput {
  return {
    whenCellIs: cell,
    andSearchTermsAre: Array.from(new Set(searches.concat(cell))),
    expectCellMatches: true,
    matchRowIdColumn: false,
  };
}

function doesNotMatch(cell: any, ...searches: string[]): TestCaseInput {
  return {
    whenCellIs: cell,
    andSearchTermsAre: Array.from(new Set(searches.concat([`BREAK${cell}`]))),
    expectCellMatches: false,
    matchRowIdColumn: false,
  };
}

function matchesRowId(...searches): TestCaseInput {
  return {
    whenCellIs: "",
    andSearchTermsAre: Array.from(new Set(searches)),
    expectCellMatches: true,
    matchRowIdColumn: true,
  };
}

function doesNotMatchRowId(...searches: string[]): TestCaseInput {
  return {
    whenCellIs: "",
    andSearchTermsAre: Array.from(new Set(searches)),
    expectCellMatches: false,
    matchRowIdColumn: true,
  };
}

const setTargetFieldAndLinkCellValuesFunc = (targetName) => {
  return async function (tablePage: TablePage, cellValue: any[]) {
    await updateRows(user, sharedPageTestData.tableA, [
      {
        id: 1,
        link_to_b: [],
      },
    ]);
    await tablePage.waitForFirstCellToBeBlank();
    const rowUpdates = [];
    const linkIds = [];
    for (let i = 0; i < cellValue.length; i++) {
      const rowId = i + 1;
      const row = { id: rowId };
      row[targetName] = cellValue[i];
      rowUpdates.push(row);
      linkIds.push(rowId);
    }
    await updateRows(user, sharedPageTestData.tableB, rowUpdates);
    await updateRows(user, sharedPageTestData.tableA, [
      {
        id: 1,
        link_to_b: linkIds,
      },
    ]);
    await tablePage.waitForFirstCellNotBeBlank();
  };
};
const fieldTypes = [
  new FieldType(
    "lookup",
    [
      {
        name: "lookup of date field",
        testCases: [
          matchesWithoutSelf(
            ["2023-01-10T00:00:00Z", "4023-01-10T12:00:00Z"],
            "10/01/4023"
          ),
        ],
        otherFieldsToMakeOrUpdate: () => [
          {
            type: "date",
            name: "target",
            table: sharedPageTestData.tableB,
            settings: {
              date_format: "EU",
              date_include_time: true,
              date_force_timezone: "UTC",
            },
          },
        ],
      },
      {
        name: "lookup of text field field",
        testCases: [matches(["test", "other"], "t", "te", "tes", "test")],
        otherFieldsToMakeOrUpdate: () => [
          {
            type: "text",
            name: "target",
            table: sharedPageTestData.tableB,
          },
        ],
      },
    ],
    {
      setCellValueFunc: setTargetFieldAndLinkCellValuesFunc("target"),
      fieldSettings: {
        target_field_name: "target",
        through_field_name: "link_to_b",
      },
      otherFieldsToMakeOrUpdate: () => [
        {
          type: "link_row",
          name: "link_to_b",
          table: sharedPageTestData.tableA,
          settings: {
            link_row_table_id: sharedPageTestData.tableB.id,
          },
        },
      ],
    }
  ),
  new FieldType(
    "link_row",
    [
      {
        name: "link of date field",
        testCases: [
          matchesWithoutSelf(
            ["2023-01-10T00:00:00Z", "4023-01-10T12:00:00Z"],
            "10/01/4023"
          ),
        ],
        otherFieldsToMakeOrUpdate: () => [
          {
            updatePrimary: true,
            type: "date",
            name: "primary",
            table: sharedPageTestData.tableB,
            settings: {
              date_format: "EU",
              date_include_time: true,
              date_force_timezone: "UTC",
            },
          },
        ],
      },
    ],
    {
      setCellValueFunc: setTargetFieldAndLinkCellValuesFunc("primary"),
      fieldSettings: () => {
        return {
          name: "link_to_b",
          link_row_table_id: sharedPageTestData.tableB.id,
        };
      },
    }
  ),
  new FieldType(
    "number",
    [
      {
        name: "number field with 4 DP",
        testCases: [
          matches(5.234, "5", "5.2", "+5.23"),
          matches(-5.234, "-5", "-5.2", "-5.23"),
          doesNotMatch(-5.234, "5", "5.2"),
        ],
        fieldSettings: { number_decimal_places: 4, number_negative: true },
      },
      {
        name: "number field with 0 DP",
        testCases: [
          matches(5, "5"),
          matches(-5, "-5"),
          doesNotMatch(-5, "5", "5.2", "a"),
        ],
        fieldSettings: { number_decimal_places: 0, number_negative: true },
      },
    ],
    {}
  ),
  new FieldType(
    "text",
    [
      {
        name: "normal text field",
        testCases: [
          // The first row is id 1!
          matchesRowId("1", "2"),
          doesNotMatchRowId("3"),
          // Some basic text cases
          matches("test", "t", "te", "tes", "test"),
          doesNotMatch("xyz", "t", "y", "z"),
          // URL cases
          matches(
            "https://google.com",
            "google",
            "google.com",
            "https://",
            ".com"
          ),
          doesNotMatch("https://www.google.com", "https://google.com"),
          // Punctuation cases
          doesNotMatch("-", "-"),
          // Email cases
          matches("test@google.com", ".com", "test", "google"),
          matches("a.b", "a", "b", "a/b"),
          // Date cases
          matches(
            "10-20-2023",
            "10",
            "20",
            "2023",
            "10-20",
            "10-20-2023",
            "20-2023",
            "10/20/2023"
          ),
          doesNotMatch("10-20-2023", "23", "0", "3"),
          // Number cases
          matches("+50", "50", "5"),
          doesNotMatch("+50", "-50", "a"),
          matches("-50", "-50", "-5"),
          doesNotMatch("-50", "+50", "50", "5"),
          matches("test -50", "-50", "-5"),
          doesNotMatch("test -50", "+50", "50", "5"),
          // Hyphenated word cases
          matches("hello-world", "hello", "world", "hello+world"),
          matches("hello.world", "hello", "world", "hello.world"),
        ],
        fieldSettings: {},
      },
    ],
    {}
  ),
];

let tablePageLoaded = false;
let testIdx = 0;

fieldTypes.forEach((fieldType) => {
  fieldType.subFieldSetups.forEach((subFieldSetup) => {
    subFieldSetup.testCases.forEach((testCase) => {
      testCase.searchTerms.forEach((searchTerm) => {
        const cellValue = testCase.matchRowIdColumn
          ? "row id"
          : testCase.cellValue;
        test(
          `${testIdx++} FullTextTest @search => ${subFieldSetup.name}
            - ${cellValue} should ${
            testCase.expectsCellToMatch ? "match" : "not match"
          }: ${searchTerm}\n`,
          { tag: "@slow" },
          async () => {
            const tablePage = new TablePage(page);

            if (!tablePageLoaded) {
              // Load the page
              await tablePage.goToTable(sharedPageTestData.tableA);
              // Wait for websockets to connect!
              await page.waitForTimeout(5000);
              tablePageLoaded = true;
            }

            if (!subFieldSetup.setup) {
              await subFieldSetup.doSetup(tablePage);
            }

            if (!testCase.setup) {
              await testCase.doSetup(tablePage);
            }
            try {
              await tablePage.openSearchContextAndSearchFor(searchTerm);

              const matchingCellsLocator = testCase.matchRowIdColumn
                ? tablePage.rowIdDivsMatchingSearch
                : tablePage.searchMatchingCells();
              const notMatchingCellsLocator = testCase.matchRowIdColumn
                ? tablePage.searchMatchingCells()
                : tablePage.rowIdDivsMatchingSearch;
              const targetCellLocator = testCase.matchRowIdColumn
                ? tablePage.firstRowIdDiv
                : tablePage.firstNonPrimaryCellWrappingColumnDiv;

              if (testCase.expectsCellToMatch) {
                await expect(
                  tablePage.rows(),
                  `expected the backend to only return one row as ${searchTerm} should match ${cellValue} however it returned either no rows or two rows including the blank one...`
                ).toHaveCount(1);
                await expect(
                  matchingCellsLocator,
                  `expected ${searchTerm} to match ${cellValue} but the frontend didn't highlight it`
                ).not.toHaveCount(0);
                await expect(
                  matchingCellsLocator,
                  `expected ${searchTerm} to match ${cellValue} but the frontend highlighted incorrectly other cells also`
                ).toHaveCount(1);
              } else {
                await expect(
                  tablePage.rows(),
                  `expected ${searchTerm} to NOT match ${cellValue} backend returned rows`
                ).toHaveCount(0);
              }

              await expect(
                notMatchingCellsLocator,
                `expected ${searchTerm} to match not match any ${
                  testCase.matchRowIdColumn ? "row ids" : "cells"
                } but it did`
              ).toHaveCount(0);

              // Search with non hiding rows
              await tablePage.openAndClickSearchToggle();
              if (testCase.expectsCellToMatch) {
                await expect(
                  matchingCellsLocator,
                  `expected ${searchTerm} to match ${cellValue} but the frontend didn't highlight it`
                ).not.toHaveCount(0);
                await expect(
                  matchingCellsLocator,
                  `expected ${searchTerm} to match ${cellValue} only but the frontend highlighted more than one cell`
                ).toHaveCount(1);
                await tablePage.expectIsSearchHighlighted(targetCellLocator);
              } else {
                await expect(
                  matchingCellsLocator,
                  `expected ${searchTerm} to NOT match ${cellValue} highlighted some cells`
                ).toHaveCount(0);
                await tablePage.expectIsNotSearchHighlighted(targetCellLocator);
              }

              await expect(
                notMatchingCellsLocator,
                `expected ${searchTerm} to match not match any ${
                  testCase.matchRowIdColumn ? "row ids" : "cells"
                } but it did`
              ).toHaveCount(0);

              await expect(tablePage.rows()).toHaveCount(2);
              await tablePage.openAndClickSearchToggle(true);
            } finally {
              if (
                testCase.last &&
                searchTerm ==
                  testCase.searchTerms[testCase.searchTerms.length - 1]
              ) {
                await subFieldSetup.tearDown(tablePage);
              }
            }
          }
        );
      });
    });
  });
});
