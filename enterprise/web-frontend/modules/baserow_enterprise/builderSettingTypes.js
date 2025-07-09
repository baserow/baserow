import { BuilderSettingType } from '@baserow/modules/builder/builderSettingTypes'
import CustomCodeSetting from '@baserow_enterprise/components/builder/CustomCodeSetting'
import EnterpriseFeatures from '@baserow_enterprise/features'
import { BuilderCustomCodePaidFeature } from '@baserow_enterprise/paidFeatures'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'

export class CustomCodeBuilderSettingType extends BuilderSettingType {
  static getType() {
    return 'custom_code'
  }

  get name() {
    return this.app.i18n.t('builderSettingTypes.customCode')
  }

  get icon() {
    return 'iconoir-code-brackets'
  }

  getOrder() {
    return 17
  }

  get component() {
    return CustomCodeSetting
  }

  isDeactivatedReason({ workspace }) {
    if (
      !this.app.$hasFeature(
        EnterpriseFeatures.BUILDER_CUSTOM_CODE,
        workspace.id
      )
    ) {
      return this.app.i18n.t('enterprise.deactivated')
    }
    return super.isDeactivatedReason({ workspace })
  }

  getDeactivatedModal({ workspace }) {
    if (
      !this.app.$hasFeature(
        EnterpriseFeatures.BUILDER_CUSTOM_CODE,
        workspace.id
      )
    ) {
      return [
        PaidFeaturesModal,
        { 'initial-selected-type': BuilderCustomCodePaidFeature.getType() },
      ]
    }
    return null
  }
}
