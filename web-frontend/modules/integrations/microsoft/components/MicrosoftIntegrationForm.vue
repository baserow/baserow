<template>
  <OAuthAccountForm v-bind="$attrs">
    <template #account-detail="{ defaultValues }">
      <template v-if="defaultValues.account_type">
        <template v-if="defaultValues.account_email">·</template>
        {{ accountTypeLabel(defaultValues.account_type) }}
      </template>
    </template>
  </OAuthAccountForm>
</template>

<script>
import OAuthAccountForm from '@baserow/modules/integrations/oauthAccount/components/OAuthAccountForm'

/**
 * The shared account form, adding whether the account is a work or school one
 * or a personal one: only work and school accounts can use Teams.
 */
export default {
  components: { OAuthAccountForm },
  inheritAttrs: false,
  methods: {
    accountTypeLabel(accountType) {
      return accountType === 'personal'
        ? this.$t('microsoftIntegrationForm.personalAccount')
        : this.$t('microsoftIntegrationForm.workAccount')
    },
  },
}
</script>
