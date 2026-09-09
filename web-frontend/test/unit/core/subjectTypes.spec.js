import {
  AgentSubjectType,
  AnonymousUserSubjectType,
  UserSubjectType,
} from '@baserow/modules/core/subjectTypes'

const names = {
  'subjectType.user': 'User',
  'subjectType.users': 'Users',
  'subjectType.anonymousUser': 'Anonymous user',
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
    [new AnonymousUserSubjectType(context), 'Anonymous user'],
    [new AgentSubjectType(context), 'Agent'],
  ])('resolves its frontend display name', (subjectType, expected) => {
    expect(subjectType.getTypeDisplayName()).toBe(expected)
  })

  test.each([
    [new UserSubjectType(context), 'Users'],
    [new AnonymousUserSubjectType(context), 'Anonymous user'],
    [new AgentSubjectType(context), 'Agents'],
  ])('resolves its plural frontend display name', (subjectType, expected) => {
    expect(subjectType.getPluralTypeDisplayName()).toBe(expected)
  })

  test.each([
    [new UserSubjectType(context), 'blue'],
    [new AnonymousUserSubjectType(context), 'blue'],
    [new AgentSubjectType(context), 'purple'],
  ])('provides its avatar color', (subjectType, expected) => {
    expect(subjectType.avatarColor).toBe(expected)
  })

  test.each([
    [new UserSubjectType(context), { id: 1, user_id: 2 }, 2],
    [new UserSubjectType(context), { id: 1 }, 1],
    [new AnonymousUserSubjectType(context), { id: 1 }, 1],
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
