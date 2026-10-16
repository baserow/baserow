import { describe, expect, test } from 'vitest'
import {
  EnterpriseAdminRoleType,
  EnterpriseBuilderRoleType,
} from '@baserow_enterprise/roleTypes'

describe('Agent application role scopes', () => {
  test('assigns administrative roles at application scope', () => {
    const app = { $i18n: { t: (key) => key } }
    for (const RoleType of [
      EnterpriseAdminRoleType,
      EnterpriseBuilderRoleType,
    ]) {
      expect(new RoleType({ app }).allowedScopeTypes).toContain('application')
      expect(new RoleType({ app }).allowedScopeTypes).not.toContain(
        'agent_builder_agent'
      )
    }
  })
})
