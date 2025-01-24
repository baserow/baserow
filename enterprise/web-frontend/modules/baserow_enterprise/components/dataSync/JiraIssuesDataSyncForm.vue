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
        :disabled="disabled"
        @focus.once="$event.target.select()"
        @blur="$v.values.jira_url.$touch()"
      />
      <template #error>
        <span v-if="$v.values.jira_url.$dirty && !$v.values.jira_url.required">
          {{ $t('error.requiredField') }}
        </span>
        <span v-else-if="$v.values.jira_url.$dirty && !$v.values.jira_url.url">
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
        :disabled="disabled"
        @focus.once="$event.target.select()"
        @blur="$v.values.jira_username.$touch()"
      />
      <template #error>
        <span
          v-if="
            $v.values.jira_username.$dirty && !$v.values.jira_username.required
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
      :protected-edit="update"
      @enabled-protected-edit="allowedValues.push('jira_api_token')"
      @disable-protected-edit="
        ;[
          allowedValues.splice(allowedValues.indexOf('jira_api_token'), 1),
          delete values['jira_api_token'],
        ]
      "
    >
      <template #label>{{ $t('jiraIssuesDataSync.apiToken') }}</template>
      <FormInput
        ref="jira_api_token"
        v-model="values.jira_api_token"
        size="large"
        :error="fieldHasErrors('jira_api_token')"
        :disabled="disabled"
        @focus.once="$event.target.select()"
        @blur="$v.values.jira_api_token.$touch()"
      />
      <template #error>
        <span
          v-if="
            $v.values.jira_api_token.$dirty &&
            !$v.values.jira_api_token.required
          "
        >
          {{ $t('error.requiredField') }}
        </span>
      </template>
    </FormGroup>

    <FormGroup
      :helper-text="$t('jiraIssuesDataSync.projectKeyHelper')"
      small-label
    >
      <template #label>{{ $t('jiraIssuesDataSync.projectKey') }}</template>
      <FormInput
        ref="jira_project_key"
        v-model="values.jira_project_key"
        size="large"
        :disabled="disabled"
        @focus.once="$event.target.select()"
      />
    </FormGroup>
  </form>
</template>

<script>
import { required, url, requiredIf } from 'vuelidate/lib/validators'
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
  data() {
    const allowedValues = ['jira_url', 'jira_username', 'jira_project_key']
    if (!this.update) {
      allowedValues.push('jira_api_token')
    }
    return {
      allowedValues,
      values: {
        jira_url: '',
        jira_username: '',
        jira_project_key: '',
      },
    }
  },
  validations() {
    return {
      values: {
        jira_url: { required, url },
        jira_username: { required },
        jira_api_token: {
          required: requiredIf(() => {
            return this.allowedValues.includes('jira_api_token')
          }),
        },
      },
    }
  },
}
</script>
