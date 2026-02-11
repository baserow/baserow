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
            <a class="licenses__instance-id-copy" @click.prevent="handleCopy()">
              {{ $t('action.copy') }}
              <Copied ref="instanceIdCopied" />
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
            >
              {{ $t('settings.enabled') }}
            </SwitchInput>
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
                :value="v$.values.account_deletion_grace_delay.$model"
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
<script setup>
import {
  ref,
  reactive,
  computed,
  watch,
  getCurrentInstance,
  onMounted,
} from 'vue'
import { useAsyncData, useNuxtApp, useHead } from '#app'
import { useStore } from 'vuex'
import { useVuelidate } from '@vuelidate/core'
import { required, integer, between, helpers } from '@vuelidate/validators'

import { notifyIf } from '@baserow/modules/core/utils/error'
import SettingsService from '@baserow/modules/core/services/settings'
import { copyToClipboard } from '@baserow/modules/database/utils/clipboard'
import { EMAIL_VERIFICATION_OPTIONS } from '@baserow/modules/core/enums'

const { $registry, $client, $baserowVersion, $i18n } = useNuxtApp()
const { t: $t } = useI18n()
const store = useStore()

useHead({ title: $i18n.t('settings.settingsTitle') })

const instanceIdCopied = ref(null)

const values = reactive({
  account_deletion_grace_delay: null,
})

const settings = computed(() => store.getters['settings/get'])

const emailVerificationOptions = computed(() => [
  {
    label: $t('settings.emailVerificationNoVerification'),
    value: EMAIL_VERIFICATION_OPTIONS.NO_VERIFICATION,
  },
  {
    label: $t('settings.emailVerificationRecommended'),
    value: EMAIL_VERIFICATION_OPTIONS.RECOMMENDED,
  },
  {
    label: $t('settings.emailVerificationEnforced'),
    value: EMAIL_VERIFICATION_OPTIONS.ENFORCED,
  },
])

const rules = computed(() => {
  return {
    values: {
      account_deletion_grace_delay: {
        required: helpers.withMessage($t('error.requiredField'), required),
        between: helpers.withMessage(
          $t('settings.invalidAccountDeletionGraceDelay'),
          between(0, 32000)
        ),
        integer: helpers.withMessage(
          $t('settings.invalidAccountDeletionGraceDelay'),
          integer
        ),
      },
    },
  }
})

const v$ = useVuelidate(rules, { values }, { $lazy: true })

const { data: instanceData } = await useAsyncData('instance-id', async () => {
  const { data } = await SettingsService($client).getInstanceID()
  return data
})

const instanceId = computed(() => instanceData.value?.instance_id ?? '')

const additionalSettingsComponents = computed(() => {
  return Object.values($registry.getAll('plugin'))
    .reduce(
      (components, plugin) =>
        components.concat(plugin.getSettingsPageComponents()),
      []
    )
    .filter((component) => component !== null)
})

const baserowVersion = computed(() => $baserowVersion)

function handleCopy() {
  copyToClipboard(instanceId.value)
  instanceIdCopied.value?.show()
}

async function updateSettings(payload) {
  v$.value.$touch()
  if (v$.value.$invalid) return
  try {
    await store.dispatch('settings/update', payload)
  } catch (error) {
    notifyIf(error, 'settings')
  }
}

function updateAccountDeletionGraceDelay() {
  const existing = settings.value.account_deletion_grace_delay
  const parsed = parseInt(v$.value.values.account_deletion_grace_delay.$model)
  if (
    !v$.value.values.account_deletion_grace_delay.$error &&
    existing !== parsed
  ) {
    updateSettings({ account_deletion_grace_delay: parsed })
  }
}

function handleAccountDeletionGraceDelayInput(event) {
  v$.value.values.account_deletion_grace_delay.$model = event
  updateAccountDeletionGraceDelay()
}

watch(
  () => settings.value.account_deletion_grace_delay,
  (val) => {
    v$.value.values.account_deletion_grace_delay.$model = val
  }
)

onMounted(() => {
  v$.value.values.account_deletion_grace_delay.$model =
    settings.value.account_deletion_grace_delay
})
</script>
