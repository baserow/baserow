import { markRaw } from 'vue'
import { Registerable } from '@baserow/modules/core/registry'
import IdentityGeneralSettingsFormComponent from '@baserow/modules/core/components/settings/identities/IdentityGeneralSettingsForm'
import IdentityMcpServerSettingsComponent from '@baserow/modules/core/components/settings/identities/IdentityMcpServerSettings'

const IdentityGeneralSettingsForm = markRaw(
  IdentityGeneralSettingsFormComponent
)
const IdentityMcpServerSettings = markRaw(IdentityMcpServerSettingsComponent)

export class IdentitySettingsType extends Registerable {
  get name() {
    return null
  }

  get icon() {
    return null
  }

  get component() {
    return null
  }

  get componentPadding() {
    return true
  }

  get showInCreate() {
    return true
  }

  isActive(workspace) {
    return true
  }

  getInitialValues(identity, context) {
    return {}
  }

  getSubmitValues(values) {
    return {}
  }
}

export class GeneralIdentitySettingsType extends IdentitySettingsType {
  static getType() {
    return 'general'
  }

  get name() {
    return this.app.$i18n.t('identities.general')
  }

  get icon() {
    return 'iconoir-settings'
  }

  get component() {
    return IdentityGeneralSettingsForm
  }

  getOrder() {
    return 1
  }

  getInitialValues(identity, { defaultRole }) {
    return {
      name: identity?.name || '',
      role_uid: identity?.role_uid || defaultRole,
    }
  }

  getSubmitValues({ name, role_uid: roleUid }) {
    return { name, role_uid: roleUid }
  }
}

export class McpServerIdentitySettingsType extends IdentitySettingsType {
  static getType() {
    return 'mcp_server'
  }

  get name() {
    return this.app.$i18n.t('mcpEndpointSettings.title')
  }

  get icon() {
    return 'iconoir-magic-wand'
  }

  get component() {
    return IdentityMcpServerSettings
  }

  get showInCreate() {
    return false
  }

  getOrder() {
    return 20
  }
}
