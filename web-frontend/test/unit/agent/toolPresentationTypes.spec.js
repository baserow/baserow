import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import cases from '@baserow_test_cases/agent_tools.json'
import coreEn from '@baserow/modules/core/locales/en.json'
import agentEn from '@baserow/modules/agent/locales/en.json'
import { groupAgentTools } from '@baserow/modules/agent/agentTools'
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
    expect(
      registry
        .getList('toolPresentation')
        .map((presenter) => presenter.getType())
        .sort()
    ).toEqual(
      cases.tools.map(({ presentation_type }) => presentation_type).sort()
    )
    for (const { name, presentation_type: type, input, facts } of cases.tools) {
      const presenter = registry.get('toolPresentation', type)
      expect(presenter.getLabel(t)).not.toMatch(/^agent\./)
      expect(presenter.getDescription(t)).not.toMatch(/^agent\./)
      for (const status of ['running', 'done', 'failed', 'stopped']) {
        const activity = toolActivity(
          step(name, status, { presentation_type: type, input, facts }),
          registry,
          t
        )
        expect(activity.title).not.toMatch(/^(agent|toolPresentation)\./)
        expect(activity.icon).toBe('iconoir-db')
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
      { title: 'Workspace activity', status: 'failed' },
    ])
    expect(groups.map(({ lines }) => lines.map(({ id }) => id))).toEqual([
      ['list_tables', 'get_table_schema'],
      [],
      ['list_views', 'list_table_rows'],
    ])
  })

  test('permission settings use the same presenters and stable presentation key', () => {
    const groups = groupAgentTools(
      [
        {
          name: 'configured_rows_action',
          presentation_type: 'create_rows',
          group: 'database',
          changes_data: true,
        },
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
            name: 'configured_rows_action',
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
})
