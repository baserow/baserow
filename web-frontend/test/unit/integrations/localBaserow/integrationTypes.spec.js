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
    expect(
      integrationType('smtp').getPromotionHint({ host: 'smtp.example.com' })
    ).toBeNull()
  })

  const promotionHint = (subject) =>
    integrationType().getPromotionHint({ authorized_subject: subject })

  test('promoting an integration says who it will run as', () => {
    testApp.authenticate({
      id: 1,
      first_name: 'Ada',
      username: 'ada@example.com',
    })

    expect(
      promotionHint({
        id: 1,
        type: 'auth.User',
        first_name: 'Ada',
        username: 'ada@example.com',
      })
    ).toBe('localBaserowIntegrationType.localBaserowPromotionHint')
    // A person can only authorize an integration as themselves, so the backend
    // authorizes it as the user promoting it.
    expect(
      promotionHint({
        id: 2,
        type: 'auth.User',
        first_name: 'Grace',
        username: 'grace@example.com',
      })
    ).toBe('localBaserowIntegrationType.localBaserowPromotionReauthorizeHint')
    // An identity belongs to the workspace and is kept.
    expect(
      promotionHint({
        id: 3,
        type: 'auth.User',
        user_type: 'identity',
        name: 'Support bot',
        trashed: false,
      })
    ).toBe('localBaserowIntegrationType.localBaserowPromotionSubjectHint')
  })

  test('promoting an integration nobody authorized says it will run as you', () => {
    // The backend authorizes it as the user promoting it.
    expect(promotionHint(null)).toBe(
      'localBaserowIntegrationType.localBaserowPromotionUnauthorizedHint'
    )
  })

  test('promoting an integration with a trashed identity has no hint', () => {
    // The backend keeps the identity, and the error message says it's trashed.
    expect(
      promotionHint({
        id: 3,
        type: 'auth.User',
        user_type: 'identity',
        name: 'Support bot',
        trashed: true,
      })
    ).toBeNull()
  })
})
