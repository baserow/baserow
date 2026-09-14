import {
  effectiveRules,
  deriveGroupPreset,
  applyGroupPreset,
  summarizeAccess,
  buildPermissionsPayload,
  normalizeWorkspaceConfig,
} from '@baserow_enterprise/utils/agentToolPermissions'

const CATALOG = [
  { name: 'list_rows', group: 'database', is_write: false },
  { name: 'create_rows', group: 'database', is_write: true },
  { name: 'delete_rows', group: 'database', is_write: true },
  { name: 'list_workflows', group: 'automation', is_write: false },
  { name: 'create_workflows', group: 'automation', is_write: true },
]
const DATABASE = CATALOG.filter((tool) => tool.group === 'database')

describe('normalizeWorkspaceConfig', () => {
  test('fills defaults and maps the legacy mode', () => {
    expect(normalizeWorkspaceConfig(undefined)).toEqual({
      access: 'everything',
      require_write_approval: true,
      tool_rules: {},
    })
    expect(normalizeWorkspaceConfig({ mode: 'read_only' }).access).toBe(
      'read_only'
    )
  })
})

describe('effectiveRules', () => {
  test('everything + approval asks for writes only', () => {
    expect(effectiveRules({}, CATALOG)).toEqual({
      list_rows: 'allow',
      create_rows: 'ask',
      delete_rows: 'ask',
      list_workflows: 'allow',
      create_workflows: 'ask',
    })
  })

  test('read only hides writes and custom rules override', () => {
    expect(effectiveRules({ access: 'read_only' }, CATALOG).create_rows).toBe(
      'off'
    )
    const rules = effectiveRules(
      {
        access: 'custom',
        tool_rules: { create_rows: 'allow', list_rows: 'ask' },
      },
      CATALOG
    )
    expect(rules.create_rows).toBe('allow')
    expect(rules.delete_rows).toBe('ask')
    expect(rules.list_rows).toBe('allow')
  })
})

describe('deriveGroupPreset / applyGroupPreset', () => {
  test('derives every preset', () => {
    const cases = [
      [
        'everything',
        { list_rows: 'allow', create_rows: 'allow', delete_rows: 'allow' },
      ],
      [
        'ask_first',
        { list_rows: 'allow', create_rows: 'ask', delete_rows: 'ask' },
      ],
      [
        'read_only',
        { list_rows: 'allow', create_rows: 'off', delete_rows: 'off' },
      ],
      ['off', { list_rows: 'off', create_rows: 'off', delete_rows: 'off' }],
      [
        'custom',
        { list_rows: 'allow', create_rows: 'ask', delete_rows: 'off' },
      ],
    ]
    for (const [preset, rules] of cases) {
      expect(deriveGroupPreset(rules, DATABASE)).toBe(preset)
      if (preset !== 'custom') {
        expect(applyGroupPreset({}, DATABASE, preset)).toEqual(rules)
      }
    }
  })

  test('applyGroupPreset leaves other groups alone', () => {
    const rules = applyGroupPreset({ create_workflows: 'ask' }, DATABASE, 'off')
    expect(rules.create_workflows).toBe('ask')
    expect(rules.list_rows).toBe('off')
  })
})

describe('summarizeAccess', () => {
  test('counts enabled and asking tools', () => {
    expect(summarizeAccess({}, CATALOG)).toEqual({
      total: 5,
      enabled: 5,
      ask: 3,
    })
    expect(summarizeAccess({ access: 'read_only' }, CATALOG)).toEqual({
      total: 5,
      enabled: 2,
      ask: 0,
    })
  })
})

describe('buildPermissionsPayload', () => {
  test('keeps a preset access when the rules equal its defaults', () => {
    const rules = effectiveRules({ access: 'read_only' }, CATALOG)
    expect(
      buildPermissionsPayload(
        { access: 'custom', tool_rules: {} },
        rules,
        CATALOG
      )
    ).toEqual({
      access: 'read_only',
      require_write_approval: true,
      tool_rules: {},
    })
  })

  test('becomes custom when the rules diverge', () => {
    const rules = { ...effectiveRules({}, CATALOG), delete_rows: 'off' }
    expect(buildPermissionsPayload({}, rules, CATALOG)).toEqual({
      access: 'custom',
      require_write_approval: true,
      tool_rules: rules,
    })
  })
})
