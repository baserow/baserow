<template>
  <form @submit.prevent="submit">
    <FormGroup
      :error="v$.github_issues_owner.$error"
      :label="$t('githubIssuesDataSync.owner')"
      required
      class="margin-bottom-2"
      :helper-text="$t('githubIssuesDataSync.ownerHelper')"
      small-label
    >
      <FormInput
        v-model="v$.github_issues_owner.$model"
        :error="v$.github_issues_owner.$error"
        size="large"
        @blur="v$.github_issues_owner.$touch"
      />
      <template #error>
        <span v-if="v$.github_issues_owner.required.$invalid">
          {{ $t('error.requiredField') }}
        </span>
      </template>
    </FormGroup>

    <FormGroup
      :error="v$.github_issues_repo.$error"
      :label="$t('githubIssuesDataSync.repo')"
      required
      class="margin-bottom-2"
      :helper-text="$t('githubIssuesDataSync.repoHelper')"
      small-label
    >
      <FormInput
        v-model="v$.github_issues_repo.$model"
        :error="v$.github_issues_repo.$error"
        size="large"
        @blur="v$.github_issues_repo.$touch"
      />
      <template #error>
        <span v-if="v$.github_issues_owner.required.$invalid">
          {{ $t('error.requiredField') }}
        </span>
      </template>
    </FormGroup>

    <FormGroup
      :error="v$.github_issues_api_token.$error"
      :label="$t('githubIssuesDataSync.apiToken')"
      required
      :helper-text="$t('githubIssuesDataSync.apiTokenHelper')"
      small-label
    >
      <FormInput
        v-model="v$.github_issues_api_token.$model"
        :error="v$.github_issues_api_token.$error"
        size="large"
        @blur="v$.github_issues_api_token.$touch"
      />
      <template #error>
        <span v-if="v$.github_issues_api_token.required.$invalid">
          {{ $t('error.requiredField') }}
        </span>
      </template>
    </FormGroup>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import { required } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'GitHubIssuesDataSyncForm',
  mixins: [form],
  data() {
    return {
      allowedValues: [
        'github_issues_owner',
        'github_issues_repo',
        'github_issues_api_token',
      ],
      values: null,
      v$: null,
    }
  },
  created() {
    const values = reactive({
      github_issues_owner: '',
      github_issues_repo: '',
      github_issues_api_token: '',
    })

    const rules = computed(() => ({
      github_issues_owner: { required },
      github_issues_repo: { required },
      github_issues_api_token: { required },
    }))
    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },
}
</script>
