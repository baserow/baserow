import { TestApp } from '@baserow/test/helpers/testApp'

describe('LocalBaserowIntegrationType', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const integrationType = (type = 'local_baserow') =>
    testApp.getRegistry().get('integration', type)

  test('a workspace integration says who it runs as in every application', () => {
    expect(
      integrationType().getWorkspaceHint({
        authorized_subject: {
          id: 1,
          type: 'auth.User',
          first_name: 'Ada',
          username: 'ada@example.com',
        },
      })
    ).toBe('localBaserowIntegrationType.localBaserowWorkspaceHint')
    expect(
      integrationType().getWorkspaceHint({
        authorized_subject: {
          id: 3,
          type: 'auth.User',
          user_type: 'identity',
          name: 'Support bot',
          trashed: false,
        },
      })
    ).toBe('localBaserowIntegrationType.localBaserowWorkspaceSubjectHint')
  })

  test('a workspace integration that runs as nobody has no hint', () => {
    // The summary and the error message already say it isn't configured.
    expect(
      integrationType().getWorkspaceHint({ authorized_subject: null })
    ).toBeNull()
    expect(
      integrationType().getWorkspaceHint({
        authorized_subject: {
          id: 3,
          type: 'auth.User',
          user_type: 'identity',
          name: 'Support bot',
          trashed: true,
        },
      })
    ).toBeNull()
  })

  test('integration types without an identity have no hint', () => {
    expect(
      integrationType('smtp').getWorkspaceHint({ host: 'smtp.example.com' })
    ).toBeNull()
  })
})
