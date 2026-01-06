<template>
  <div>
    <FormGroup
      required
      :label="$t('slackBotForm.tokenLabel')"
      small-label
      class="margin-bottom-3"
      :error-message="getFirstErrorMessage('token')"
    >
      <FormInput
        v-model="values.token"
        :placeholder="$t('slackBotForm.tokenPlaceholder')"
      />
    </FormGroup>
    <hr />
    <FormGroup
      :label="$t('slackBotForm.supportHeading')"
      small-label
      class="margin-top-3 margin-bottom-2"
    >
      <p class="margin-bottom-2">{{ $t('slackBotForm.supportDescription') }}</p>
      <Expandable card class="margin-bottom-2">
        <template #header="{ toggle, expanded }">
          <div class="flex flex-100 justify-content-space-between">
            <a @click="toggle">
              {{ $t('slackBotForm.supportSetupHeading') }}
              <Icon
                :icon="
                  expanded
                    ? 'iconoir-nav-arrow-down'
                    : 'iconoir-nav-arrow-right'
                "
                type="secondary"
              />
            </a>
          </div>
        </template>
        <template #default>
          <p class="margin-bottom-2">
            {{ $t('slackBotForm.supportSetupDescription') }}
          </p>
          <ol class="slack-bot-form__instructions">
            <li>
              <i18n-t keypath="slackBotForm.supportSetupStep1">
                <template #link>
                  <a href="https://api.slack.com/apps" target="_blank">{{
                    $t('slackBotForm.supportSetupStep1Link')
                  }}</a>
                </template>
              </i18n-t>
            </li>
            <li>{{ $t('slackBotForm.supportSetupStep2') }}</li>
            <li>{{ $t('slackBotForm.supportSetupStep3') }}</li>
            <li>
              <i18n-t keypath="slackBotForm.supportSetupStep4">
                <template #scope>
                  <pre>chat:write</pre>
                </template>
              </i18n-t>
            </li>
          </ol>
        </template>
      </Expandable>
      <Expandable card class="margin-bottom-2">
        <template #header="{ toggle, expanded }">
          <div class="flex flex-100 justify-content-space-between">
            <a @click="toggle">
              {{ $t('slackBotForm.supportPairingHeading') }}
              <Icon
                :icon="
                  expanded
                    ? 'iconoir-nav-arrow-down'
                    : 'iconoir-nav-arrow-right'
                "
                type="secondary"
              />
            </a>
          </div>
        </template>
        <template #default>
          <ol class="slack-bot-form__instructions">
            <li>{{ $t('slackBotForm.supportPairingStep1') }}</li>
            <li>{{ $t('slackBotForm.supportPairingStep2') }}</li>
            <li>
              <i18n-t keypath="slackBotForm.supportPairingStep3">
                <template #command>
                  <pre>/invite @yourAppName yourChannel</pre>
                </template>
              </i18n-t>
            </li>
          </ol>
        </template>
      </Expandable>
    </FormGroup>
  </div>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import { useVuelidate } from '@vuelidate/core'
import { required, helpers } from '@vuelidate/validators'

export default {
  mixins: [form],
  props: {
    application: {
      type: Object,
      required: true,
    },
  },
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      values: { token: '' },
      allowedValues: ['token'],
    }
  },
  validations() {
    return {
      values: {
        token: {
          required,
          startsWith: helpers.withMessage(
            this.$t('slackBotForm.tokenMustStartWith'),
            (value) => !value || value.startsWith('xoxb-')
          ),
        },
      },
    }
  },
}
</script>
