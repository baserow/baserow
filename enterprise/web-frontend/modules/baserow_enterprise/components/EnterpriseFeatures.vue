<template>
  <ul class="premium-features">
    <li
      v-if="!hiddenFeatures.includes(enterpriseFeatures.SSO)"
      class="premium-features__feature"
    >
      <i class="iconoir-check premium-features__feature-icon"></i>
      {{ $t('enterpriseFeatures.sso') }}
    </li>
    <li
      v-if="!hiddenFeatures.includes(enterpriseFeatures.RBAC)"
      class="premium-features__feature"
    >
      <i class="iconoir-check premium-features__feature-icon"></i>
      {{ $t('enterpriseFeatures.rbac') }}
    </li>
    <li
      v-if="!hiddenFeatures.includes(enterpriseFeatures.AUDIT_LOG)"
      class="premium-features__feature"
    >
      <i class="iconoir-check premium-features__feature-icon"></i>
      {{ $t('enterpriseFeatures.auditLogs') }}
    </li>
    <li
      v-if="!hiddenFeatures.includes(enterpriseFeatures.DATA_SYNC)"
      class="premium-features__feature"
    >
      <i class="iconoir-check premium-features__feature-icon"></i>
      {{ $t('enterpriseFeatures.dataSync') }}
    </li>
    <li
      v-if="!hiddenFeatures.includes(enterpriseFeatures.ENTERPRISE_SETTINGS)"
      class="premium-features__feature"
    >
      <i class="iconoir-check premium-features__feature-icon"></i>
      {{ $t('enterpriseFeatures.coBranding') }}
    </li>
    <li
      v-if="!hiddenFeatures.includes(enterpriseFeatures.ADVANCED_WEBHOOKS)"
      class="premium-features__feature"
    >
      <i class="iconoir-check premium-features__feature-icon"></i>
      {{ $t('enterpriseFeatures.advancedWebhooks') }}
    </li>
    <li
      v-if="
        !hiddenFeatures.includes(enterpriseFeatures.FIELD_LEVEL_PERMISSIONS)
      "
      class="premium-features__feature"
    >
      <i class="iconoir-check premium-features__feature-icon"></i>
      {{ $t('enterpriseFeatures.fieldLevelPermissions') }}
    </li>
    <li
      v-if="!hiddenFeatures.includes(enterpriseFeatures.SUPPORT)"
      class="premium-features__feature"
    >
      <i class="iconoir-check premium-features__feature-icon"></i>
      {{ $t('enterpriseFeatures.support') }}
    </li>
  </ul>
</template>

<script>
import EnterpriseFeaturesObject from '@baserow_enterprise/features'

export default {
  name: 'EnterpriseFeatures',
  computed: {
    enterpriseFeatures() {
      return EnterpriseFeaturesObject
    },
    hiddenFeatures() {
      const { EnterprisePlugin } = require('@baserow_enterprise/plugins')
      return this.$registry
        .get('plugin', EnterprisePlugin.getType())
        .getVisuallyHiddenFeatures()
    },
  },
}
</script>
