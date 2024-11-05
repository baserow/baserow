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
        v-model="values.jira_url"
        size="large"
        :error="fieldHasErrors('jira_url')"
        @focus.once="$event.target.select()"
        @blur="v$.values.jira_url.$touch()"
      />
      <template #error>
        <span v-if="v$.values.jira_url.$dirty && !v$.values.jira_url.required">
          {{ $t('error.requiredField') }}
        </span>
        <span v-else-if="v$.values.jira_url.$dirty && !v$.values.jira_url.url">
          {{ $t('error.invalidURL') }}
        </span>
      </template>
    </FormGroup>

    <FormGroup
      :error="fieldHasErrors('jira_username')"
      :helper-text="$t('jiraIssuesDataSync.usernameHelper')"
      required
      small-label
      class="margin-bottom-2"
    >
      <template #label>{{ $t('jiraIssuesDataSync.jiraUsername') }}</template>
      <FormInput
        ref="jira_username"
        v-model="values.jira_username"
        size="large"
        :error="fieldHasErrors('jira_username')"
        @focus.once="$event.target.select()"
        @blur="v$.values.jira_username.$touch()"
      />
      <template #error>
        <span
          v-if="
            v$.values.jira_username.$dirty && !v$.values.jira_username.required
          "
        >
          {{ $t('error.requiredField') }}
        </span>
      </template>
    </FormGroup>

    <FormGroup
      :error="fieldHasErrors('jira_api_token')"
      :helper-text="$t('jiraIssuesDataSync.apiTokenHelper')"
      required
      small-label
      class="margin-bottom-2"
    >
      <template #label>{{ $t('jiraIssuesDataSync.apiToken') }}</template>
      <FormInput
        ref="jira_api_token"
        v-model="values.jira_api_token"
        size="large"
        :error="fieldHasErrors('jira_api_token')"
        @focus.once="$event.target.select()"
        @blur="v$.values.jira_api_token.$touch()"
      />
      <template #error>
        <span
          v-if="
            v$.values.jira_api_token.$dirty &&
            !v$.values.jira_api_token.required
          "
        >
          {{ $t('error.requiredField') }}
        </span>
      </template>
    </FormGroup>

    <FormGroup
      :helper-text="$t('jiraIssuesDataSync.projectKeyHelper')"
      required
      small-label
    >
      <template #label>{{ $t('jiraIssuesDataSync.projectKey') }}</template>
      <FormInput
        ref="jira_project_key"
        v-model="values.jira_project_key"
        size="large"
        @focus.once="$event.target.select()"
      />
    </FormGroup>
  </form>
</template>

<script>
import { required, url } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'JiraIssuesDataSyncForm',
  mixins: [form],
  data() {
    return {
      allowedValues: [
        'jira_url',
        'jira_username',
        'jira_api_token',
        'jira_project_key',
      ],
      values: {
        jira_url: '',
        jira_username: '',
        jira_api_token: '',
        jira_project_key: '',
      },
    }
  },
  validations: {
    values: {
      jira_url: { required, url },
      jira_username: { required },
      jira_api_token: { required },
    },
  },
}
</script>
