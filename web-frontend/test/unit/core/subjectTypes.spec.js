import { describe, expect, test, vi } from 'vitest'

import {
  AnonymousUserSubjectType,
  UserSubjectType,
} from '@baserow/modules/core/subjectTypes'

const names = {
  'subjectType.user': 'User',
  'subjectType.users': 'Users',
  'subjectType.anonymousUser': 'Anonymous user',
  'subjectType.identity': 'Identity',
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
    [new UserSubjectType(context), undefined, 'User'],
    [new AnonymousUserSubjectType(context), undefined, 'Anonymous user'],
    [new UserSubjectType(context), { user_type: 'identity' }, 'Identity'],
  ])('resolves its frontend display name', (subjectType, subject, expected) => {
    expect(subjectType.getTypeDisplayName(subject)).toBe(expected)
  })

  test.each([
    [new UserSubjectType(context), 'Users'],
    [new AnonymousUserSubjectType(context), 'Anonymous user'],
  ])('resolves its plural frontend display name', (subjectType, expected) => {
    expect(subjectType.getPluralTypeDisplayName()).toBe(expected)
  })

  test('holds its roles directly', () => {
    expect(new UserSubjectType(context).holdsRolesDirectly).toBe(true)
  })

  test.each([
    [new UserSubjectType(context), { id: 1, user_id: 2 }, 2],
    [new UserSubjectType(context), { id: 1 }, 1],
    [new UserSubjectType(context), { id: 'auth.User:3', subject_id: 3 }, 3],
    [new AnonymousUserSubjectType(context), { id: 1 }, 1],
  ])('resolves a subject id', (subjectType, subject, expected) => {
    expect(subjectType.getId(subject)).toBe(expected)
  })

  test.each([
    [new UserSubjectType(context), { id: 1, user_id: 2 }, 'auth.User:2'],
    [new UserSubjectType(context), { id: 1 }, 'auth.User:1'],
  ])('keys a subject by type and id', (subjectType, subject, expected) => {
    expect(subjectType.getKey(subject)).toBe(expected)
  })

  test.each([
    [
      new UserSubjectType(context),
      { user_id: 2, permissions: 'ADMIN' },
      'ADMIN',
    ],
    [new UserSubjectType(context), { id: 2 }, null],
    [new UserSubjectType(context), { id: 1, role_uid: 'BUILDER' }, 'BUILDER'],
  ])(
    'reads the workspace role off a subject',
    (subjectType, subject, expected) => {
      expect(subjectType.getWorkspaceRoleUid(subject)).toBe(expected)
    }
  )

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
      avatarComponent: expect.any(Function),
    })
    expect(subjectType.getBadge()).toBeNull()
  })

  test('describes an identity as an invite option with its badge', () => {
    const subjectType = new UserSubjectType({ app: app() })
    const identity = {
      id: 4,
      name: 'Smith',
      email: null,
      user_type: 'identity',
    }
    expect(subjectType.getInviteOption(identity)).toMatchObject({
      key: 'auth.User:4',
      name: 'Smith',
      subtitle: 'Identity',
      search: 'Smith',
      avatarComponent: expect.any(Function),
    })
    expect(subjectType.getSubtitle(identity)).toBeNull()
    expect(subjectType.getBadge(identity)).toBe('Identity')
  })

  test('offers users and identities but not anonymous visitors for role assignments', () => {
    expect(new UserSubjectType({ app: app() }).isEnabled({ id: 1 })).toBe(true)
    expect(
      new AnonymousUserSubjectType({ app: app() }).isEnabled({ id: 1 })
    ).toBe(false)
  })

  test('fetches the subjects a role can be given to', async () => {
    const users = [{ user_id: 8 }]
    const client = {
      get: vi.fn().mockResolvedValue({
        data: { results: [{ id: 4 }], next: null },
      }),
    }
    const withIdentities = {
      $client: client,
      $featureFlagIsEnabled: () => true,
    }
    await expect(
      new UserSubjectType({
        app: app(withIdentities),
      }).fetchAssignableSubjects({ id: 12, users })
    ).resolves.toEqual([{ user_id: 8 }, { id: 4 }])

    // Without the flag or the permission to list identities, none are fetched.
    client.get.mockClear()
    for (const restricted of [
      { $featureFlagIsEnabled: () => false },
      { $hasPermission: () => false },
    ]) {
      await expect(
        new UserSubjectType({
          app: app({ ...withIdentities, ...restricted }),
        }).fetchAssignableSubjects({ id: 12, users })
      ).resolves.toBe(users)
    }
    expect(client.get).not.toHaveBeenCalled()
  })
})
