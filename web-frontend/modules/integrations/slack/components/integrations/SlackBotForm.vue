<template>
  <div class="slack-bot-form">
    <template v-if="!hasToken">
      <h4 class="slack-bot-form__heading">
        {{ $t('slackBotForm.heading') }}
      </h4>
      <p class="slack-bot-form__intro">{{ $t('slackBotForm.intro') }}</p>
    </template>
    <ol class="slack-bot-form__steps">
      <li v-if="!hasToken" class="slack-bot-form__step">
        <div class="slack-bot-form__step-marker">1</div>
        <div class="slack-bot-form__step-body">
          <div class="slack-bot-form__step-row">
            <div>
              <div class="slack-bot-form__step-title">
                {{ $t('slackBotForm.stepCreateTitle') }}
              </div>
              <div class="slack-bot-form__step-description">
                {{ $t('slackBotForm.stepCreateDescription') }}
              </div>
            </div>
            <Button
              tag="a"
              type="secondary"
              icon="iconoir-open-new-window"
              class="slack-bot-form__create"
              :href="createAppUrl"
              target="_blank"
              rel="noopener noreferrer"
            >
              {{ $t('slackBotForm.createApp') }}
            </Button>
          </div>
          <div class="slack-bot-form__step-note">
            {{ $t('slackBotForm.stepCreateAdmin') }}
          </div>
        </div>
      </li>
      <li v-if="!hasToken" class="slack-bot-form__step">
        <div class="slack-bot-form__step-marker">2</div>
        <div class="slack-bot-form__step-body">
          <div class="slack-bot-form__step-title">
            {{ $t('slackBotForm.stepInstallTitle') }}
          </div>
          <div class="slack-bot-form__step-description">
            {{ $t('slackBotForm.stepInstallDescription') }}
          </div>
        </div>
      </li>
      <li class="slack-bot-form__step">
        <div v-if="!hasToken" class="slack-bot-form__step-marker">3</div>
        <div class="slack-bot-form__step-body">
          <FormGroup
            :required="!hasToken"
            :label="
              hasToken
                ? $t('slackBotForm.tokenLabel')
                : $t('slackBotForm.stepTokenTitle')
            "
            small-label
            :helper-text="
              hasToken
                ? $t('slackBotForm.tokenConfigured')
                : $t('slackBotForm.stepTokenDescription')
            "
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
        </div>
      </li>
    </ol>
    <div class="slack-bot-form__info">
      <i class="slack-bot-form__info-icon iconoir-info-empty"></i>
      <i18n-t scope="global" keypath="slackBotForm.privateChannels" tag="span">
        <template #command>
          <code class="slack-bot-form__command">/invite @Baserow</code>
        </template>
      </i18n-t>
    </div>
    <Alert type="warning" class="slack-bot-form__warning">
      <template #title>{{
        $t('integrationCreateEditModal.warningTitle')
      }}</template>
      <p>{{ $t('slackBotIntegrationType.slackBotWarning') }}</p>
    </Alert>
  </div>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import { useVuelidate } from '@vuelidate/core'
import { helpers } from '@vuelidate/validators'
import { getSlackCreateAppUrl } from '@baserow/modules/integrations/slack/manifest'

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
    createAppUrl() {
      return getSlackCreateAppUrl()
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
