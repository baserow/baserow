<template>
  <div>
    <FormGroup
      :required="!hasToken"
      :label="$t('slackBotForm.tokenLabel')"
      small-label
      class="margin-bottom-3"
      :helper-text="hasToken ? $t('slackBotForm.tokenConfigured') : ''"
      :error-message="getFirstErrorMessage('token')"
    >
      <FormInput
        v-model="values.token"
        type="password"
        autocomplete="new-password"
        :placeholder="
          hasToken
            ? $t('slackBotForm.tokenKeepPlaceholder')
            : $t('slackBotForm.tokenPlaceholder')
        "
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
              <i18n-t scope="global" keypath="slackBotForm.supportSetupStep1">
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
              <i18n-t scope="global" keypath="slackBotForm.supportSetupStep4">
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
              <i18n-t scope="global" keypath="slackBotForm.supportPairingStep3">
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
import { helpers } from '@vuelidate/validators'

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
      // An empty field is dropped on submit to keep the stored token.
      values: { token: null },
      allowedValues: ['token'],
    }
  },
  computed: {
    hasToken() {
      return this.defaultValues.has_token === true
    },
  },
  methods: {
    getFormValues(deep = false) {
      const values = Object.assign(
        {},
        this.values,
        this.getChildFormsValues(deep)
      )
      if (!values.token) {
        delete values.token
      }
      return values
    },
  },
  validations() {
    return {
      values: {
        token: {
          // A token that is already saved need not be retyped, but a brand new
          // integration still needs one.
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            (value) => this.hasToken || !!value
          ),
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
