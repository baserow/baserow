import { markRaw } from 'vue'
import { IdentitySettingsType } from '@baserow/modules/core/identitySettingsTypes'
import EnterpriseFeatures from '@baserow_enterprise/features'
import IdentityTeamsFormFieldComponent from '@baserow_enterprise/components/identities/IdentityTeamsFormField'

const IdentityTeamsFormField = markRaw(IdentityTeamsFormFieldComponent)

export class EnterpriseTeamsIdentitySettingsType extends IdentitySettingsType {
  static getType() {
    return 'teams'
  }

  get name() {
    return this.app.$i18n.t('enterpriseIdentities.teams')
  }

  get icon() {
    return 'baserow-icon-team'
  }

  get component() {
    return IdentityTeamsFormField
  }

  getOrder() {
    return 10
  }

  isActive(workspace) {
    return this.app.$hasFeature(EnterpriseFeatures.TEAMS, workspace.id)
  }

  getInitialValues(identity) {
    return { team_ids: (identity?.teams || []).map((team) => team.id) }
  }

  getSubmitValues({ team_ids: teamIds }) {
    return { team_ids: teamIds }
  }
}
