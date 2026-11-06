import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import cases from '@baserow_test_cases/agent_tools.json'
import coreEn from '@baserow/modules/core/locales/en.json'
import agentEn from '@baserow/modules/agent/locales/en.json'
import { groupAgentTools } from '@baserow/modules/agent/agentTools'
import { STEP_ERROR_CODE } from '@baserow/modules/core/chatRuns/constants'
import {
  groupToolSteps,
  toolActivity,
} from '@baserow/modules/core/toolPresentationTypes'

const { createI18n } = await vi.importActual('vue-i18n')
const i18n = createI18n({
  legacy: false,
  locale: 'en',
  messages: { en: { ...coreEn, ...agentEn } },
  missingWarn: false,
  fallbackWarn: false,
})
const t = i18n.global.t

describe('Agent tool presentations', () => {
  let testApp
  let registry

  beforeEach(() => {
    testApp = new TestApp()
    registry = testApp.getRegistry()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const step = (tool, status = 'running', extra = {}) => ({
    id: tool,
    tool,
    status,
    changes_data: !tool.startsWith('list_') && tool !== 'get_table_schema',
    input: {},
    facts: {},
    ...extra,
  })

  test('every backend contract example has an actually registered presenter', () => {
    expect(Object.values(STEP_ERROR_CODE).sort()).toEqual(
      [...cases.step_error_codes].sort()
    )
    for (const error_code of cases.step_error_codes) {
      expect(
        toolActivity(step('list_tables', 'failed', { error_code }), registry, t)
          .failureHint
      ).toBeTruthy()
    }
    expect(
      registry
        .getList('toolPresentation')
        .map((presenter) => presenter.getType())
        .sort()
    ).toEqual(cases.tools.map(({ name }) => name).sort())
    for (const { name, input, facts } of cases.tools) {
      const presenter = registry.get('toolPresentation', name)
      expect(presenter.getLabel(t)).not.toMatch(/^agent\./)
      expect(presenter.getDescription(t)).not.toMatch(/^agent\./)
      for (const status of ['running', 'done', 'failed', 'stopped']) {
        const activity = toolActivity(
          step(name, status, { input, facts }),
          registry,
          t
        )
        expect(activity.title).not.toMatch(/^(agent|toolPresentation)\./)
        expect(activity.input).toEqual(
          step(name).changes_data && input.values
            ? { values: input.values, truncated: false }
            : null
        )
      }
    }
  })

  test.each([
    [1, 'Creating 1 row', 'Added 1 row to Tasks'],
    [3, 'Creating 3 rows', 'Added 3 rows to Tasks'],
    [0, 'Creating 0 rows', 'Added 0 rows to Tasks'],
  ])(
    'translates requested and actual row counts: %s',
    (count, running, done) => {
      const data = step('create_rows', 'running', {
        input: { requested_count: count },
        facts: { count, table: 'Tasks' },
      })

      expect(toolActivity(data, registry, t).title).toBe(running)
      expect(toolActivity({ ...data, status: 'done' }, registry, t).title).toBe(
        done
      )
    }
  )

  test('completed changes use confirmed counts and missing counts keep action labels', () => {
    const data = step('create_rows', 'done', {
      input: { requested_count: 9 },
      facts: { count: 2 },
    })

    expect(toolActivity(data, registry, t).title).toBe('Added 2 rows')
    expect(toolActivity({ ...data, facts: {} }, registry, t).title).toBe(
      'Create rows'
    )
    expect(toolActivity({ ...data, status: 'failed' }, registry, t).title).toBe(
      'Create rows'
    )
  })

  test('shows confirmed read counts and newly created table names', () => {
    expect(
      toolActivity(
        step('list_table_rows', 'done', {
          facts: { count: 3, table: 'Tasks' },
        }),
        registry,
        t
      ).title
    ).toBe('Read 3 rows from Tasks')
    expect(
      toolActivity(
        step('list_table_rows', 'done', { facts: { table: 'Tasks' } }),
        registry,
        t
      ).title
    ).toBe('Read rows from Tasks')
    expect(
      toolActivity(
        step('get_table_schema', 'running', { input: { requested_count: 3 } }),
        registry,
        t
      ).title
    ).toBe('Reading the structure of 3 tables')
    expect(
      toolActivity(
        step('create_tables', 'done', {
          facts: { count: 1, table: 'Projects' },
        }),
        registry,
        t
      ).title
    ).toBe('Created 1 table: Projects')
  })

  test.each([
    [
      { count: 0, existing_count: 1, existing_table: 'Tasks' },
      'create_tables',
      'Used the existing table Tasks',
    ],
    [
      { count: 0, existing_count: 2, existing_table: 'Tasks, Notes' },
      'create_tables',
      'Used 2 existing tables: Tasks, Notes',
    ],
    [
      {
        count: 1,
        table: 'Projects',
        existing_count: 1,
        existing_table: 'Tasks',
      },
      'create_tables',
      'Created 1 table: Projects',
    ],
    [
      { count: 0, table: 'Tasks', existing_count: 1 },
      'create_views',
      'Skipped 1 view in Tasks: name already exists',
    ],
    [
      { count: 0, table: 'Tasks', existing_count: 2 },
      'create_views',
      'Skipped 2 views in Tasks: names already exist',
    ],
    [
      { count: 0, existing_count: 1 },
      'create_views',
      'Skipped 1 view: name already exists',
    ],
    [
      { count: 0, existing_count: 2 },
      'create_views',
      'Skipped 2 views: names already exist',
    ],
  ])(
    'reports reused tables and skipped views accurately: %j',
    (facts, tool, title) => {
      expect(
        toolActivity(step(tool, 'done', { facts }), registry, t).title
      ).toBe(title)
    }
  )

  test.each([null, [], { requested_count: -1 }, { requested_count: '3' }])(
    'malformed summaries retain a tool-specific action label: %j',
    (input) => {
      expect(
        toolActivity(step('create_rows', 'running', { input }), registry, t)
          .title
      ).toBe('Creating rows')
    }
  )

  test('groups only consecutive workspace reads and preserves call order', () => {
    const groups = groupToolSteps(
      [
        step('list_tables', 'done'),
        step('get_table_schema', 'running'),
        step('create_rows', 'done'),
        step('list_views', 'failed'),
        step('list_table_rows', 'stopped'),
      ],
      registry,
      t
    )

    expect(groups.map(({ title, status }) => ({ title, status }))).toEqual([
      { title: 'Looking at your workspace', status: 'running' },
      { title: 'Create rows', status: 'done' },
      { title: 'Workspace activity', status: 'stopped' },
    ])
    expect(groups.map(({ lines }) => lines.map(({ id }) => id))).toEqual([
      ['list_tables', 'get_table_schema'],
      [],
      ['list_views', 'list_table_rows'],
    ])
  })

  test('permission settings use the same presenters as tool activity', () => {
    const groups = groupAgentTools(
      [
        { name: 'create_rows', group: 'database', changes_data: true },
        { name: 'new_tool', group: 'custom', changes_data: false },
      ],
      registry,
      t
    )

    expect(groups).toMatchObject([
      {
        label: 'Databases',
        tools: [
          {
            name: 'create_rows',
            label: 'Create rows',
            description: 'Add new rows to a table',
            changesData: true,
          },
        ],
      },
      {
        label: 'custom',
        tools: [{ name: 'new_tool', label: 'new_tool', description: '' }],
      },
    ])
  })

  test('the last successful read sets the summary while earlier failures stay on their lines', () => {
    const [group] = groupToolSteps(
      [
        step('list_tables', 'done', { id: 'a' }),
        step('list_table_rows', 'failed', {
          id: 'b',
          error_code: STEP_ERROR_CODE.NOT_FOUND,
        }),
        step('list_table_rows', 'failed', {
          id: 'c',
          error_code: STEP_ERROR_CODE.PERMISSION_DENIED,
        }),
        step('list_table_rows', 'done', {
          id: 'd',
          facts: { count: 22, table: 'Projects' },
        }),
      ],
      registry,
      t
    )
    expect(group.status).toBe('done')
    expect(group.title).toBe('Looked at your workspace')
    expect(group.failureHint).toBe('')
    expect(group.lines[1].failureHint).toBe(
      'Not found or not accessible to the agent.'
    )
    expect(group.lines[2].failureHint).toBe(
      'Permission denied for this operation.'
    )
    expect(group.lines.map(({ status }) => status)).toEqual([
      'done',
      'failed',
      'failed',
      'done',
    ])
    expect(group.lines.at(-1).title).toBe('Read 22 rows from Projects')
  })

  test.each([
    [['failed', 'done', 'stopped'], 'stopped', 'Workspace activity', ''],
    [
      ['done', 'failed'],
      'failed',
      'Workspace activity',
      'Not found or not accessible to the agent.',
    ],
    [['running', 'done'], 'running', 'Looking at your workspace', ''],
    [['running', 'failed'], 'running', 'Looking at your workspace', ''],
  ])(
    'a workspace group of %j calls summarizes as %s',
    (statuses, status, title, failureHint) => {
      const calls = statuses.map((callStatus, index) =>
        step('list_table_rows', callStatus, {
          id: String(index),
          error_code: STEP_ERROR_CODE.NOT_FOUND,
        })
      )
      expect(groupToolSteps(calls, registry, t)[0]).toMatchObject({
        status,
        title,
        failureHint,
      })
    }
  )
})
