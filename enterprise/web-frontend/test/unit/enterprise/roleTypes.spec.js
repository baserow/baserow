import { expect, test } from 'vitest'

import RolesService from '@baserow/modules/core/services/roles'
import * as roleTypes from '@baserow_enterprise/roleTypes'

test.each([true, false])(
  'exposes the active invitation default with RBAC enabled: %s',
  (rbacEnabled) => {
    const app = {
      $i18n: { t: (key) => key },
      $hasFeature: () => rbacEnabled,
    }
    const registry = {
      getAll: () =>
        Object.values(roleTypes).map((RoleType) => new RoleType({ app })),
    }
    const { data } = RolesService(null, null, registry).get({ id: 1 })

    expect(
      data
        .filter(
          (role) =>
            role.isVisible &&
            !role.isDeactivated &&
            role.isDefaultForInvitations
        )
        .map(({ uid }) => uid)
    ).toEqual([rbacEnabled ? 'VIEWER' : 'MEMBER'])
    expect(
      data.find(({ uid }) => uid === 'NO_ROLE_LOW_PRIORITY').invitationSubtitle
    ).toBe('shareScope.pendingNoWorkspaceRole')
    expect(
      data.find(({ uid }) => uid === 'VIEWER').invitationSubtitle
    ).toBeNull()
  }
)
