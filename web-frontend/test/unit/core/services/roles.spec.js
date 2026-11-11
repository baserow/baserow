import { expect, test } from 'vitest'

import RolesService from '@baserow/modules/core/services/roles'
import { AdminRoleType, MemberRoleType } from '@baserow/modules/core/roleTypes'

test('exposes Member as the basic invitation default', () => {
  const app = { $i18n: { t: (key) => key } }
  const registry = {
    getAll: () => ({
      admin: new AdminRoleType({ app }),
      member: new MemberRoleType({ app }),
    }),
  }
  const { data } = RolesService(null, null, registry).get({ id: 1 })

  expect(
    data.filter((role) => role.isDefaultForInvitations).map(({ uid }) => uid)
  ).toEqual(['MEMBER'])
  expect(data.map(({ invitationSubtitle }) => invitationSubtitle)).toEqual([
    null,
    null,
  ])
})
