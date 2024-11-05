<template>
  <div class="layout__col-2-scroll">
    <div class="admin-settings">
      <h1>{{ $t('settings.settingsTitle') }}</h1>
      <div class="admin-settings__group">
        <div class="admin-settings__item">
          <div class="admin-settings__label">
            <div class="admin-settings__name">
              {{ $t('settings.baserowInstanceId') }}
            </div>
            <div class="admin-settings__description">
              {{ $t('settings.instanceIdDescription') }}
            </div>
          </div>
          <div class="admin-settings__control">
            {{ instanceId }}
            <a
              class="licenses__instance-id-copy"
              @click.prevent="
                ;[copyToClipboard(instanceId), $refs.instanceIdCopied.show()]
              "
            >
              {{ $t('action.copy') }}
              <Copied ref="instanceIdCopied"></Copied>
            </a>
          </div>
        </div>
        <div class="admin-settings__item">
          <div class="admin-settings__label">
            <div class="admin-settings__name">
              {{ $t('settings.baserowVersion') }}
            </div>
            <div class="admin-settings__description">
              {{ $t('settings.baserowVersionDescription') }}
            </div>
          </div>
          <div class="admin-settings__control">
            {{ baserowVersion }}
          </div>
        </div>
        <div class="admin-settings__item">
          <div class="admin-settings__label">
            <div class="admin-settings__name">
              {{ $t('settings.settingsVerifyImportSignature') }}
            </div>
            <div class="admin-settings__description">
              {{ $t('settings.settingsVerifyImportSignatureDescription') }}
            </div>
          </div>
          <div class="admin-settings__control">
            <SwitchInput
              :value="settings.verify_import_signature"
              @input="updateSettings({ verify_import_signature: $event })"
              >{{ $t('settings.enabled') }}</SwitchInput
            >
          </div>
        </div>
      </div>
      <div class="admin-settings__group">
        <h2 class="admin-settings__group-title">
          {{ $t('settings.accountRestrictions') }}
        </h2>
        <div class="admin-settings__item">
          <div class="admin-settings__label">
            <div class="admin-settings__name">
              {{ $t('settings.settingAllowNewAccountsName') }}
            </div>
            <div class="admin-settings__description">
              {{ $t('settings.settingAllowNewAccountsDescription') }}
            </div>
          </div>
          <div class="admin-settings__control">
            <SwitchInput
              :value="settings.allow_new_signups"
              @input="updateSettings({ allow_new_signups: $event })"
              >{{ $t('settings.enabled') }}</SwitchInput
            >
          </div>
        </div>
        <div v-if="!settings.allow_new_signups" class="admin-settings__item">
          <div class="admin-settings__label">
            <div class="admin-settings__name">
              {{
                $t('settings.settingAllowSignupsViaWorkspaceInvitationsName')
              }}
            </div>
            <div class="admin-settings__description">
              {{
                $t(
                  'settings.settingAllowSignupsViaWorkspaceInvitationDescription'
                )
              }}
            </div>
          </div>
          <div class="admin-settings__control">
            <SwitchInput
              :value="settings.allow_signups_via_workspace_invitations"
              @input="
                updateSettings({
                  allow_signups_via_workspace_invitations: $event,
                })
              "
              >{{ $t('settings.enabled') }}</SwitchInput
            >
          </div>
        </div>
        <div class="admin-settings__item">
          <div class="admin-settings__label">
            <div class="admin-settings__name">
              {{ $t('settings.settingAllowResetPasswordName') }}
            </div>
            <div class="admin-settings__description">
              {{ $t('settings.settingAllowResetPasswordDescription') }}
            </div>
          </div>
          <div class="admin-settings__control">
            <SwitchInput
              :value="settings.allow_reset_password"
              @input="updateSettings({ allow_reset_password: $event })"
              >{{ $t('settings.enabled') }}</SwitchInput
            >
            <div v-show="!settings.allow_reset_password" class="warning">
              {{ $t('settings.settingAllowResetPasswordWarning') }}
            </div>
          </div>
        </div>
        <div class="admin-settings__item">
          <div class="admin-settings__label">
            <div class="admin-settings__name">
              {{ $t('settings.settingAllowNonStaffCreateWorkspaceOperation') }}
            </div>
            <div class="admin-settings__description">
              {{
                $t(
                  'settings.settingAllowNonStaffCreateWorkspaceOperationDescription'
                )
              }}
            </div>
          </div>
          <div class="admin-settings__control">
            <SwitchInput
              :value="settings.allow_global_workspace_creation"
              @input="
                updateSettings({ allow_global_workspace_creation: $event })
              "
              >{{ $t('settings.enabled') }}</SwitchInput
            >
            <div
              v-show="settings.allow_global_workspace_creation"
              class="warning"
            >
              {{
                $t(
                  'settings.settingAllowNonStaffCreateWorkspaceOperationWarning'
                )
              }}
            </div>
          </div>
        </div>
      </div>
      <div class="admin-settings__group">
        <h2 class="admin-settings__group-title">
          {{ $t('settings.userSettings') }}
        </h2>
        <div class="admin-settings__item">
          <div class="admin-settings__label">
            <div class="admin-settings__name">
              {{ $t('settings.emailVerification') }}
            </div>
            <div class="admin-settings__description">
              {{ $t('settings.emailVerificationDescription') }}
            </div>
          </div>
          <div class="admin-settings__control">
            <RadioGroup
              :model-value="settings.email_verification"
              :options="emailVerificationOptions"
              @input="updateSettings({ email_verification: $event })"
            ></RadioGroup>
          </div>
        </div>
        <div class="admin-settings__item">
          <div class="admin-settings__label">
            <div class="admin-settings__name">
              {{ $t('settings.settingUserDeletionGraceDelay') }}
            </div>
            <div class="admin-settings__description">
              {{ $t('settings.settingUserDeletionGraceDelayDescription') }}
            </div>
          </div>
          <div class="admin-settings__control">
            <FormGroup :error="v$.values.account_deletion_grace_delay.$error">
              <FormInput
                v-model="v$.values.account_deletion_grace_delay.$model"
                :error="v$.values.account_deletion_grace_delay.$error"
                type="number"
                size="large"
                @input="handleAccountDeletionGraceDelayInput($event)"
              ></FormInput>

              <template #error>
                {{
                  v$.values.account_deletion_grace_delay.$errors[0]?.$message
                }}
              </template>
            </FormGroup>
          </div>
        </div>
      </div>
      <div class="admin-settings__group">
        <h2 class="admin-settings__group-title">
          {{ $t('settings.maintenance') }}
        </h2>
        <div class="admin-settings__item">
          <div class="admin-settings__label">
            <div class="admin-settings__name">
              {{ $t('settings.settingTrackWorkspaceUsage') }}
            </div>
            <div class="admin-settings__description">
              {{ $t('settings.settingTrackWorkspaceUsageDescription') }}
            </div>
          </div>
          <div class="admin-settings__control">
            <SwitchInput
              :value="settings.track_workspace_usage"
              @input="updateSettings({ track_workspace_usage: $event })"
              >{{ $t('settings.enabled') }}</SwitchInput
            >
          </div>
        </div>
      </div>
      <component
        :is="component"
        v-for="(component, index) in additionalSettingsComponents"
        :key="index"
      ></component>
    </div>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'

import { reactive, getCurrentInstance } from 'vue'
import { required, integer, between, helpers } from '@vuelidate/validators'
import { mapGetters } from 'vuex'

import { notifyIf } from '@baserow/modules/core/utils/error'
import SettingsService from '@baserow/modules/core/services/settings'
import { copyToClipboard } from '@baserow/modules/database/utils/clipboard'

import { EMAIL_VERIFICATION_OPTIONS } from '@baserow/modules/core/enums'

export default {
  layout: 'app',
  middleware: 'staff',
  setup() {
    const instance = getCurrentInstance()
    const values = reactive({
      account_deletion_grace_delay: null,
    })

    const rules = {
      values: {
        account_deletion_grace_delay: {
          required: helpers.withMessage(
            instance.proxy.$t('error.requiredField'),
            required
          ),
          between: helpers.withMessage(
            instance.proxy.$t('settings.invalidAccountDeletionGraceDelay'),
            between(0, 32000)
          ),
          integer: helpers.withMessage(
            instance.proxy.$t('settings.invalidAccountDeletionGraceDelay'),
            integer
          ),
        },
      },
    }

    const v$ = useVuelidate(rules, { values }, { $lazy: true })

    return { values, v$, loading: false }
  },

  async asyncData({ app }) {
    const { data } = await SettingsService(app.$client).getInstanceID()
    return { instanceId: data.instance_id }
  },

  data() {
    return {
      emailVerificationOptions: [
        {
          label: this.$t('settings.emailVerificationNoVerification'),
          value: EMAIL_VERIFICATION_OPTIONS.NO_VERIFICATION,
        },
        {
          label: this.$t('settings.emailVerificationRecommended'),
          value: EMAIL_VERIFICATION_OPTIONS.RECOMMENDED,
        },
        {
          label: this.$t('settings.emailVerificationEnforced'),
          value: EMAIL_VERIFICATION_OPTIONS.ENFORCED,
        },
      ],
    }
  },
  computed: {
    additionalSettingsComponents() {
      return Object.values(this.$registry.getAll('plugin'))
        .reduce(
          (components, plugin) =>
            components.concat(plugin.getSettingsPageComponents()),
          []
        )
        .filter((component) => component !== null)
    },
    ...mapGetters({
      settings: 'settings/get',
    }),
    EMAIL_VERIFICATION_OPTIONS() {
      return EMAIL_VERIFICATION_OPTIONS
    },
    baserowVersion() {
      return this.$baserowVersion
    },
  },
  watch: {
    'settings.account_deletion_grace_delay'(value) {
      this.values.account_deletion_grace_delay = value
    },
    'values.account_deletion_grace_delay'(value) {
      if (this.dataInitialized) {
        this.updateSettings({ account_deletion_grace_delay: value })
      }
    },
  },
  mounted() {
    this.values.account_deletion_grace_delay =
      this.settings.account_deletion_grace_delay
  },
  methods: {
    async updateSettings(values) {
      this.v$.$touch()
      if (this.v$.$invalid) {
        return
      }
      try {
        await this.$store.dispatch('settings/update', values)
      } catch (error) {
        notifyIf(error, 'settings')
      }
    },
    copyToClipboard(value) {
      copyToClipboard(value)
    },
    updateAccountDeletionGraceDelay() {
      const existingValue = this.settings.account_deletion_grace_delay

      if (
        !this.v$.values.account_deletion_grace_delay.$error &&
        existingValue !== parseInt(this.values.account_deletion_grace_delay)
      ) {
        this.updateSettings({
          account_deletion_grace_delay: parseInt(
            this.values.account_deletion_grace_delay
          ),
        })
      }
    },
    handleAccountDeletionGraceDelayInput(event) {
      this.v$.values.account_deletion_grace_delay.$touch()
      this.updateAccountDeletionGraceDelay(event)
    },
  },
}
</script>
