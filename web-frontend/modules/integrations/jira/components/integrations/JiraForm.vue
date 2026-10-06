<template>
  <div>
    <FormGroup
      required
      :label="$t('jiraForm.urlLabel')"
      :helper-text="$t('jiraForm.urlHelp')"
      small-label
      class="margin-bottom-2"
      :error-message="getFirstErrorMessage('url')"
    >
      <FormInput
        v-model="v$.values.url.$model"
        :placeholder="$t('jiraForm.urlPlaceholder')"
      />
    </FormGroup>
    <FormGroup
      required
      :label="$t('jiraForm.authenticationLabel')"
      :helper-text="$t('jiraForm.authenticationHelp')"
      small-label
      class="margin-bottom-2"
    >
      <Dropdown v-model="values.authentication" :show-search="false">
        <DropdownItem
          :name="$t('jiraForm.apiToken')"
          value="API_TOKEN"
        ></DropdownItem>
        <DropdownItem
          :name="$t('jiraForm.personalAccessToken')"
          value="PERSONAL_ACCESS_TOKEN"
        ></DropdownItem>
      </Dropdown>
    </FormGroup>
    <FormGroup
      v-if="values.authentication === 'API_TOKEN'"
      required
      :label="$t('jiraForm.usernameLabel')"
      :helper-text="$t('jiraForm.usernameHelp')"
      small-label
      class="margin-bottom-2"
      :error-message="getFirstErrorMessage('username')"
    >
      <FormInput
        v-model="v$.values.username.$model"
        :placeholder="$t('jiraForm.usernamePlaceholder')"
      />
    </FormGroup>
    <FormGroup
      :required="!hasApiToken"
      :label="
        values.authentication === 'API_TOKEN'
          ? $t('jiraForm.apiTokenLabel')
          : $t('jiraForm.personalAccessTokenLabel')
      "
      :helper-text="
        hasApiToken
          ? $t('jiraForm.tokenConfigured')
          : values.authentication === 'API_TOKEN'
            ? $t('jiraForm.apiTokenHelp')
            : $t('jiraForm.personalAccessTokenHelp')
      "
      small-label
      class="margin-bottom-2"
      :error-message="getFirstErrorMessage('api_token')"
    >
      <FormInput
        v-model="values.api_token"
        type="password"
        autocomplete="new-password"
        :placeholder="hasApiToken ? $t('jiraForm.tokenKeepPlaceholder') : ''"
      />
    </FormGroup>
    <p class="integration-setup-steps__note">
      {{ $t('jiraForm.permissionsNote') }}
    </p>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { helpers, url } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'JiraForm',
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
      // An empty token is dropped on submit to keep the stored one.
      values: {
        url: '',
        authentication: 'API_TOKEN',
        username: '',
        api_token: null,
      },
      allowedValues: ['url', 'authentication', 'username', 'api_token'],
    }
  },
  computed: {
    hasApiToken() {
      return this.defaultValues.has_api_token === true
    },
  },
  methods: {
    getFormValues(deep = false) {
      const values = Object.assign(
        {},
        this.values,
        this.getChildFormsValues(deep)
      )
      if (!values.api_token) {
        delete values.api_token
      }
      return values
    },
  },
  validations() {
    return {
      values: {
        url: {
          required: helpers.withMessage(
            this.$t('jiraForm.required'),
            (value) => !!value
          ),
          url: helpers.withMessage(this.$t('jiraForm.invalidUrl'), url),
        },
        username: {
          required: helpers.withMessage(
            this.$t('jiraForm.required'),
            (value) => this.values.authentication !== 'API_TOKEN' || !!value
          ),
        },
        api_token: {
          required: helpers.withMessage(
            this.$t('jiraForm.required'),
            (value) => this.hasApiToken || !!value
          ),
        },
      },
    }
  },
}
</script>
