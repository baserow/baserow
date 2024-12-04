<template>
  <form @submit.prevent="submit">
    <FormGroup
      :error="v$.jira_url.$error"
      :helper-text="$t('jiraIssuesDataSync.urlHelper')"
      required
      small-label
      class="margin-bottom-2"
    >
      <template #label>{{ $t('jiraIssuesDataSync.jiraUrl') }}</template>
      <FormInput
        ref="jira_url"
        v-model="v$.jira_url.$model"
        size="large"
        :error="v$.jira_url.$error"
        @focus.once="$event.target.select()"
        @blur="v$.jira_url.$touch"
      />
      <template #error>
        <span v-if="v$.jira_url.required.$invalid">
          {{ $t('error.requiredField') }}
        </span>
        <span v-else-if="v$.values.jira_url.url.$invalid">
          {{ $t('error.invalidURL') }}
        </span>
      </template>
    </FormGroup>

    <FormGroup
      :error="v$.jira_username.$error"
      :helper-text="$t('jiraIssuesDataSync.usernameHelper')"
      required
      small-label
      class="margin-bottom-2"
    >
      <template #label>{{ $t('jiraIssuesDataSync.jiraUsername') }}</template>
      <FormInput
        ref="jira_username"
        v-model="v$.jira_username.$model"
        size="large"
        :error="v$.jira_username.$error"
        @focus.once="$event.target.select()"
        @blur="v$.jira_username.$touch"
      />
      <template #error>
        <span v-if="v$.jira_username.required.$invalid">
          {{ $t('error.requiredField') }}
        </span>
      </template>
    </FormGroup>

    <FormGroup
      :error="v$.jira_api_token.$error"
      :helper-text="$t('jiraIssuesDataSync.apiTokenHelper')"
      required
      small-label
      class="margin-bottom-2"
    >
      <template #label>{{ $t('jiraIssuesDataSync.apiToken') }}</template>
      <FormInput
        ref="jira_api_token"
        v-model="v$.jira_api_token.$model"
        size="large"
        :error="v$.jira_api_token.$error"
        @focus.once="$event.target.select()"
        @blur="v$.jira_api_token.$touch"
      />
      <template #error>
        <span v-if="v$.jira_api_token.required.$invalid">
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
        v-model="v$.jira_project_key.$model"
        size="large"
        @focus.once="$event.target.select()"
      />
    </FormGroup>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
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
      values: null,
      v$: null,
    }
  },
  created() {
    const values = reactive({
      jira_url: '',
      jira_username: '',
      jira_api_token: '',
      jira_project_key: '',
    })

    const rules = computed(() => ({
      jira_url: { required, url },
      jira_username: { required },
      jira_api_token: { required },
      jira_project_key: {},
    }))
    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },
}
</script>
