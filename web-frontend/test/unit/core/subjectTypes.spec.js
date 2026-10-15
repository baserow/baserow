import { describe, expect, test, vi } from 'vitest'

import {
  AgentSubjectType,
  UserSubjectType,
} from '@baserow/modules/core/subjectTypes'

const names = {
  'subjectType.user': 'User',
  'subjectType.users': 'Users',
  'subjectType.agent': 'Agent',
  'subjectType.agents': 'Agents',
}

const context = {
  app: {
    $i18n: {
      t: (key) => names[key],
    },
  },
}

describe('SubjectType', () => {
  test.each([
    [new UserSubjectType(context), 'User'],
    [new AgentSubjectType(context), 'Agent'],
  ])('resolves its frontend display name', (subjectType, expected) => {
    expect(subjectType.getTypeDisplayName()).toBe(expected)
  })

  test.each([
    [new UserSubjectType(context), 'Users'],
    [new AgentSubjectType(context), 'Agents'],
  ])('resolves its plural frontend display name', (subjectType, expected) => {
    expect(subjectType.getPluralTypeDisplayName()).toBe(expected)
  })

  test.each([
    [new UserSubjectType(context), 'blue'],
    [new AgentSubjectType(context), 'purple'],
  ])('provides its avatar color', (subjectType, expected) => {
    expect(subjectType.avatarColor).toBe(expected)
  })

  test.each([
    [new UserSubjectType(context), { id: 1, user_id: 2 }, 2],
    [new UserSubjectType(context), { id: 1 }, 1],
    [new AgentSubjectType(context), { id: 1 }, 1],
  ])('resolves a subject id', (subjectType, subject, expected) => {
    expect(subjectType.getId(subject)).toBe(expected)
  })

  test.each([
    [{ name: 'Workspace member' }, 'Workspace member'],
    [{ first_name: 'Role subject' }, 'Role subject'],
    [{ email: 'user@example.com' }, 'user@example.com'],
  ])('resolves a user display name', (subject, expected) => {
    expect(new UserSubjectType(context).getDisplayName(subject)).toBe(expected)
  })
})

describe('SubjectType invite options', () => {
  const app = (overrides = {}) => ({
    $i18n: { t: (key) => names[key] },
    $featureFlagIsEnabled: () => true,
    $hasPermission: () => true,
    ...overrides,
  })

  test('describes a user as an invite option', () => {
    const subjectType = new UserSubjectType({ app: app() })
    expect(
      subjectType.getInviteOption({
        id: 1,
        user_id: 8,
        name: 'Mark Delgado',
        email: 'mark@x.com',
      })
    ).toMatchObject({
      key: 'auth.User:8',
      type: 'auth.User',
      id: 8,
      name: 'Mark Delgado',
      email: 'mark@x.com',
      subtitle: 'mark@x.com',
      search: 'Mark Delgado mark@x.com',
      initials: 'MD',
      icon: 'iconoir-user',
      color: 'blue',
    })
    expect(subjectType.getBadge()).toBeNull()
  })

  test('describes an agent as an invite option with its badge', () => {
    const subjectType = new AgentSubjectType({ app: app() })
    expect(subjectType.getInviteOption({ id: 4, name: 'Smith' })).toMatchObject(
      {
        key: 'core.Agent:4',
        name: 'Smith',
        subtitle: 'Agent',
        search: 'Smith',
        initials: '',
        icon: 'baserow-icon-agent',
        color: 'purple',
      }
    )
    expect(subjectType.getSubtitle({ id: 4 })).toBeNull()
    expect(subjectType.getBadge()).toBe('Agent')
  })

  test('only enables agents behind the feature flag', () => {
    expect(new UserSubjectType({ app: app() }).isEnabled({ id: 1 })).toBe(true)
    expect(
      new AgentSubjectType({
        app: app({ $featureFlagIsEnabled: () => false }),
      }).isEnabled({ id: 1 })
    ).toBe(false)
  })

  test('fetches the subjects a role can be given to', async () => {
    const users = [{ user_id: 8 }]
    await expect(
      new UserSubjectType({ app: app() }).fetchAssignableSubjects({ users })
    ).resolves.toBe(users)

    const client = {
      get: vi.fn().mockResolvedValue({
        data: { results: [{ id: 4 }], next: null },
      }),
    }
    await expect(
      new AgentSubjectType({
        app: app({ $client: client }),
      }).fetchAssignableSubjects({ id: 12 })
    ).resolves.toEqual([{ id: 4 }])

    // Without the permission to list agents, none are fetched.
    client.get.mockClear()
    await expect(
      new AgentSubjectType({
        app: app({ $client: client, $hasPermission: () => false }),
      }).fetchAssignableSubjects({ id: 12 })
    ).resolves.toEqual([])
    expect(client.get).not.toHaveBeenCalled()
  })
})
