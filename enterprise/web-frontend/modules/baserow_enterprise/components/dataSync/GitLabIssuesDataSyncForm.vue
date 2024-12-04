<template>
  <form @submit.prevent="submit">
    <FormGroup
      :error="fieldHasErrors('gitlab_url')"
      :helper-text="$t('gitlabIssuesDataSync.urlHelper')"
      required
      small-label
      class="margin-bottom-2"
    >
      <template #label>{{ $t('gitlabIssuesDataSync.url') }}</template>
      <FormInput
        ref="gitlab_url"
        v-model="values.gitlab_url"
        size="large"
        :error="fieldHasErrors('gitlab_url')"
        @focus.once="$event.target.select()"
        @blur="v$.values.gitlab_url.$touch()"
      />
      <template #error>
        <span
          v-if="v$.values.gitlab_url.$dirty && !v$.values.gitlab_url.required"
        >
          {{ $t('error.requiredField') }}
        </span>
        <span v-else-if="v$.values.gitlab_url.ur.$invalid">
          {{ $t('error.invalidURL') }}
        </span>
      </template>
    </FormGroup>

    <FormGroup
      :error="v$.gitlab_project_id.$error"
      :label="$t('gitlabIssuesDataSync.projectId')"
      required
      class="margin-bottom-2"
      :helper-text="$t('gitlabIssuesDataSync.projectIdHelper')"
      small-label
    >
      <FormInput
        v-model="v$.gitlab_project_id.$model"
        :error="v$.gitlab_project_id.$error"
        size="large"
        @blur="v$.gitlab_project_id.$touch"
      />
      <template #error>
        <span v-if="v$.gitlab_project_id.required.$invalid">
          {{ $t('error.requiredField') }}
        </span>
      </template>
    </FormGroup>

    <FormGroup
      :error="v$.gitlab_access_token.$error"
      :label="$t('gitlabIssuesDataSync.accessToken')"
      required
      class="margin-bottom-2"
      :helper-text="$t('gitlabIssuesDataSync.accessTokenHelper')"
      small-label
    >
      <FormInput
        v-model="v$.gitlab_access_token.$model"
        :error="v$.gitlab_access_token.$error"
        size="large"
        @blur="v$.gitlab_access_token.$touch"
      />
      <template #error>
        <span v-if="!v$.gitlab_access_token.required.$invalid">
          {{ $t('error.requiredField') }}
        </span>
      </template>
    </FormGroup>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import { required, url } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'GitLabIssuesDataSyncForm',
  mixins: [form],
  data() {
    return {
      allowedValues: ['gitlab_url', 'gitlab_project_id', 'gitlab_access_token'],
      values: null,
      v$: null,
      values: {
        gitlab_url: 'https://gitlab.com',
        gitlab_project_id: '',
        gitlab_access_token: '',
      },
    }
  },
  created() {
    const values = reactive({
      gitlab_url: 'https://gitlab.com',
      gitlab_project_id: '',
      gitlab_access_token: '',
    })

    const rules = computed(() => ({
      gitlab_url: { required, url },
      gitlab_project_id: { required },
      gitlab_access_token: { required },
    }))
    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },
}
</script>
