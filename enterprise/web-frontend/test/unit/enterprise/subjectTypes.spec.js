import { TeamSubjectType } from '@baserow_enterprise/subjectTypes'

describe('TeamSubjectType', () => {
  const subjectType = new TeamSubjectType({
    app: {
      $i18n: {
        t: (key) =>
          ({ 'subjectType.team': 'Team', 'subjectType.teams': 'Teams' })[key],
      },
    },
  })

  test('resolves a team id', () => {
    expect(subjectType.getId({ id: 1 })).toBe(1)
  })

  test('keys a team and has no workspace role of its own', () => {
    expect(subjectType.getKey({ id: 1 })).toBe('baserow_enterprise.Team:1')
    expect(
      subjectType.getWorkspaceRoleUid({ id: 1, default_role: 'ADMIN' })
    ).toBe(null)
  })

  test('passes its roles on to its members instead of holding them', () => {
    expect(subjectType.holdsRolesDirectly).toBe(false)
  })

  test('resolves its display names', () => {
    expect(subjectType.getTypeDisplayName()).toBe('Team')
    expect(subjectType.getPluralTypeDisplayName()).toBe('Teams')
  })
})
