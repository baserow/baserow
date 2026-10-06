import { describe, test, expect } from 'vitest'

import { AllowIfTemplateOperationPermissionManagerType } from '@baserow/modules/core/permissionManagerTypes'
import {
  state as makeState,
  mutations,
  getters,
} from '@baserow/modules/core/store/templateWorkspace'

function makeManager(registeredIds = []) {
  const state = makeState()
  registeredIds.forEach((id) => mutations.ADD(state, id))
  const $store = {
    getters: {
      'templateWorkspace/isTemplateWorkspace':
        getters.isTemplateWorkspace(state),
    },
  }
  return new AllowIfTemplateOperationPermissionManagerType({
    app: { $store },
  })
}

const OPERATION = 'database.table.read'

describe('AllowIfTemplateOperationPermissionManagerType', () => {
  test('allows operations in a locally registered template workspace', () => {
    const manager = makeManager([10])
    const permissions = {
      workspace_template_ids: [],
      allowed_operations_on_templates: [OPERATION],
    }
    expect(manager.hasPermission(permissions, OPERATION, {}, 10)).toBe(true)
  })

  test('still allows workspaces listed in workspace_template_ids', () => {
    const manager = makeManager()
    const permissions = {
      workspace_template_ids: [10],
      allowed_operations_on_templates: [OPERATION],
    }
    expect(manager.hasPermission(permissions, OPERATION, {}, 10)).toBe(true)
  })

  test('works without workspace_template_ids in the payload', () => {
    const manager = makeManager([10])
    const permissions = { allowed_operations_on_templates: [OPERATION] }
    expect(manager.hasPermission(permissions, OPERATION, {}, 10)).toBe(true)
  })

  test('does not answer for unregistered workspaces', () => {
    const manager = makeManager([10])
    const permissions = {
      workspace_template_ids: [],
      allowed_operations_on_templates: [OPERATION],
    }
    expect(manager.hasPermission(permissions, OPERATION, {}, 11)).toBe(
      undefined
    )
  })

  test('does not answer for operations not allowed on templates', () => {
    const manager = makeManager([10])
    const permissions = {
      workspace_template_ids: [],
      allowed_operations_on_templates: [OPERATION],
    }
    expect(
      manager.hasPermission(permissions, 'database.table.delete', {}, 10)
    ).toBe(undefined)
  })
})
