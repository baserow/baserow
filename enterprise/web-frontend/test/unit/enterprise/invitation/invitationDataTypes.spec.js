import { describe, expect, test } from 'vitest'

import {
  ScopesInvitationDataType,
  TeamsInvitationDataType,
} from '@baserow_enterprise/invitationDataTypes'

const app = {
  $i18n: {
    t: (key, params) =>
      params ? `${key}(${Object.values(params).join('|')})` : key,
  },
}

const workspace = {
  _: { roles: [{ uid: 'EDITOR', name: 'Editor' }] },
}

describe('invitation data types', () => {
  test('describes the objects an invitation grants a role on', () => {
    const type = new ScopesInvitationDataType({ app })

    expect(
      type.getTargets(workspace, {
        scopes: [
          {
            scope_type: 'database_table',
            scope_id: 1,
            name: 'Customers',
            role: 'EDITOR',
          },
          { scope_type: 'application', scope_id: 2, name: 'CRM', role: 'X' },
          { scope_type: 'database_view', scope_id: 3, name: 'Open', role: 'X' },
          { scope_type: 'unknown', scope_id: 4, name: 'Other', role: 'X' },
        ],
      })
    ).toEqual([
      {
        name: 'Customers',
        description:
          'invitationDataType.scopeTarget(Customers|invitationDataType.scopeTypeTable|Editor)',
      },
      {
        name: 'CRM',
        description:
          'invitationDataType.scopeTarget(CRM|invitationDataType.scopeTypeApplication|X)',
      },
      {
        name: 'Open',
        description:
          'invitationDataType.scopeTarget(Open|invitationDataType.scopeTypeView|X)',
      },
      {
        name: 'Other',
        description:
          'invitationDataType.scopeTarget(Other|invitationDataType.scopeTypeOther|X)',
      },
    ])
    expect(type.getTargets(workspace, {})).toEqual([])
  })

  test('describes the teams an invitation adds the person to', () => {
    const type = new TeamsInvitationDataType({ app })

    expect(
      type.getTargets(workspace, { teams: [{ id: 1, name: 'Ops' }] })
    ).toEqual([
      { name: 'Ops', description: 'invitationDataType.teamTarget(Ops)' },
    ])
    expect(type.getTargets(workspace, {})).toEqual([])
  })

  test('lists objects before teams', () => {
    expect(new ScopesInvitationDataType({ app }).getOrder()).toBeLessThan(
      new TeamsInvitationDataType({ app }).getOrder()
    )
  })
})
