<template>
  <form @submit.prevent="submit">
    <FormGroup
      :error="fieldHasErrors('jira_url')"
      :helper-text="$t('jiraIssuesDataSync.urlHelper')"
      required
      small-label
      class="margin-bottom-2"
    >
      <template #label>{{ $t('jiraIssuesDataSync.jiraUrl') }}</template>
      <FormInput
        ref="jira_url"
        v-model="v$.values.jira_url.$model"
        size="large"
        :error="fieldHasErrors('jira_url')"
        :disabled="disabled"
        @focus.once="$event.target.select()"
        @blur="v$.values.jira_url.$touch"
      />
      <template #error>
        {{ v$.values.jira_url.$errors[0]?.$message }}
      </template>
    </FormGroup>

    <FormGroup
      :error="fieldHasErrors('jira_authentication')"
      :helper-text="$t('jiraIssuesDataSync.authenticationHelper')"
      required
      small-label
      class="margin-bottom-2"
    >
      <template #label>{{
        $t('jiraIssuesDataSync.authenticationLabel')
      }}</template>
      <Dropdown
        v-model="values.jira_authentication"
        :disabled="disabled"
        size="large"
      >
        <DropdownItem name="API Token" value="API_TOKEN"></DropdownItem>
        <DropdownItem
          name="Personal access token"
          value="PERSONAL_ACCESS_TOKEN"
        ></DropdownItem>
      </Dropdown>
    </FormGroup>

    <FormGroup
      v-if="values.jira_authentication === 'API_TOKEN'"
      :error="fieldHasErrors('jira_username')"
      :helper-text="$t('jiraIssuesDataSync.usernameHelper')"
      required
      small-label
      class="margin-bottom-2"
    >
      <template #label>{{ $t('jiraIssuesDataSync.jiraUsername') }}</template>
      <FormInput
        ref="jira_username"
        v-model="v$.values.jira_username.$model"
        size="large"
        :error="fieldHasErrors('jira_username')"
        :disabled="disabled"
        @focus.once="$event.target.select()"
        @blur="v$.values.jira_username.$touch"
      />
      <template #error>
        {{ v$.values.jira_username.$errors[0]?.$message }}
      </template>
    </FormGroup>

    <FormGroup
      :error="fieldHasErrors('jira_api_token')"
      :helper-text="
        values.jira_authentication === 'API_TOKEN'
          ? $t('jiraIssuesDataSync.apiTokenHelper')
          : $t('jiraIssuesDataSync.personalAccessTokenHelper')
      "
      required
      small-label
      class="margin-bottom-2"
      :protected-edit="update"
      @enabled-protected-edit="values.jira_api_token = ''"
      @disable-protected-edit="values.jira_api_token = undefined"
    >
      <template #label>{{
        values.jira_authentication === 'API_TOKEN'
          ? $t('jiraIssuesDataSync.apiToken')
          : $t('jiraIssuesDataSync.personalAccessToken')
      }}</template>
      <FormInput
        ref="jira_api_token"
        v-model="v$.values.jira_api_token.$model"
        size="large"
        :error="fieldHasErrors('jira_api_token')"
        :disabled="disabled"
        @focus.once="$event.target.select()"
        @blur="v$.values.jira_api_token.$touch"
      />
      <template #error>
        {{ v$.values.jira_api_token.$errors[0]?.$message }}
      </template>
    </FormGroup>

    <FormGroup
      :helper-text="$t('jiraIssuesDataSync.projectKeyHelper')"
      small-label
    >
      <template #label>{{ $t('jiraIssuesDataSync.projectKey') }}</template>
      <FormInput
        ref="jira_project_key"
        v-model="v$.values.jira_project_key.$model"
        size="large"
        :disabled="disabled"
        @focus.once="$event.target.select()"
      />
    </FormGroup>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required, requiredIf, url, helpers } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'JiraIssuesDataSyncForm',
  mixins: [form],
  props: {
    update: {
      type: Boolean,
      required: false,
      default: false,
    },
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    const allowedValues = [
      'jira_url',
      'jira_authentication',
      'jira_username',
      'jira_project_key',
      'jira_api_token',
    ]
    return {
      allowedValues,
      values: {
        jira_url: '',
        jira_authentication: 'API_TOKEN',
        jira_username: '',
        jira_project_key: '',
        jira_api_token: this.update ? undefined : '',
      },
    }
  },
  validations() {
    return {
      values: {
        jira_url: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          url: helpers.withMessage(this.$t('error.invalidURL'), url),
        },
        jira_username: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            requiredIf(() => {
              return this.values.jira_authentication === 'API_TOKEN'
            })
          ),
        },
        jira_api_token: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            requiredIf(() => {
              return this.values.jira_api_token !== undefined
            })
          ),
        },
        jira_project_key: {},
      },
    }
  },
}
</script>
