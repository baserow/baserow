import { TeamSubjectType } from '@baserow_enterprise/subjectTypes'

describe('TeamSubjectType', () => {
  const subjectType = new TeamSubjectType({
    app: {
      $i18n: {
        t: (key) =>
          ({
            'subjectType.team': 'Team',
            'subjectType.teams': 'Teams',
            'subjectType.teamMembers': '2 members',
          })[key],
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

  test('describes a team as an invite option with its badge', () => {
    expect(
      subjectType.getInviteOption({
        id: 3,
        name: 'Management',
        subject_count: 2,
      })
    ).toMatchObject({
      key: 'baserow_enterprise.Team:3',
      name: 'Management',
      subtitle: '2 members',
      search: 'Management',
      initials: '',
      icon: 'iconoir-community',
      color: 'neutral',
    })
    expect(subjectType.getBadge()).toBe('Team')
  })
})
