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
            <!-- eslint-disable-next-line vue/no-v-html vue/no-v-text-v-html-on-component -->
            <li v-html="$t('slackBotForm.supportSetupStep1')"></li>
            <li>{{ $t('slackBotForm.supportSetupStep2') }}</li>
            <li>{{ $t('slackBotForm.supportSetupStep3') }}</li>
            <!-- eslint-disable-next-line vue/no-v-html vue/no-v-text-v-html-on-component -->
            <li v-html="$t('slackBotForm.supportSetupStep4')"></li>
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
            <!-- eslint-disable-next-line vue/no-v-html vue/no-v-text-v-html-on-component -->
            <li v-html="$t('slackBotForm.supportPairingStep3')"></li>
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
