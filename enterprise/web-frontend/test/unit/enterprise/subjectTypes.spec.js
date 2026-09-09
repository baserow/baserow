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

  test('resolves its display names', () => {
    expect(subjectType.getTypeDisplayName()).toBe('Team')
    expect(subjectType.getPluralTypeDisplayName()).toBe('Teams')
  })
})
