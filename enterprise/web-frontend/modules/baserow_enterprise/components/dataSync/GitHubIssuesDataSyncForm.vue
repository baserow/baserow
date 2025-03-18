<template>
  <form @submit.prevent="submit">
    <FormGroup
      :error="fieldHasErrors('github_issues_owner')"
      :label="$t('githubIssuesDataSync.owner')"
      required
      class="margin-bottom-2"
      :helper-text="$t('githubIssuesDataSync.ownerHelper')"
      small-label
    >
      <FormInput
        v-model="v$.values.github_issues_owner.$model"
        :error="fieldHasErrors('github_issues_owner')"
        :disabled="disabled"
        size="large"
        @blur="v$.values.github_issues_owner.$touch"
      />
      <template #error>
        <span>
          {{ v$.values.github_issues_owner.$errors[0]?.$message }}
        </span>
      </template>
    </FormGroup>

    <FormGroup
      :error="fieldHasErrors('github_issues_repo')"
      :label="$t('githubIssuesDataSync.repo')"
      required
      class="margin-bottom-2"
      :helper-text="$t('githubIssuesDataSync.repoHelper')"
      small-label
    >
      <FormInput
        v-model="v$.values.github_issues_repo.$model"
        :error="fieldHasErrors('github_issues_repo')"
        :disabled="disabled"
        size="large"
        @blur="v$.values.github_issues_repo.$touch"
      />
      <template #error>
        {{ v$.values.github_issues_repo.$errors[0]?.$message }}
      </template>
    </FormGroup>

    <FormGroup
      :error="fieldHasErrors('github_issues_api_token')"
      :label="$t('githubIssuesDataSync.apiToken')"
      required
      :helper-text="$t('githubIssuesDataSync.apiTokenHelper')"
      small-label
      :protected-edit="update"
      @enabled-protected-edit="values.github_issues_api_token = ''"
      @disable-protected-edit="values.github_issues_api_token = undefined"
    >
      <FormInput
        v-model="v$.values.github_issues_api_token.$model"
        :error="fieldHasErrors('github_issues_api_token')"
        :disabled="disabled"
        size="large"
        @blur="v$.values.github_issues_api_token.$touch"
      />
      <template #error>
        {{ v$.values.github_issues_api_token.$errors[0]?.$message }}
      </template>
    </FormGroup>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required, requiredIf, helpers } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'GitHubIssuesDataSyncForm',
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
    return {
      allowedValues: [
        'github_issues_owner',
        'github_issues_repo',
        'github_issues_api_token',
      ],
      values: {
        github_issues_owner: '',
        github_issues_repo: '',
        github_issues_api_token: this.update ? undefined : '',
      },
    }
  },
  validations() {
    return {
      values: {
        github_issues_owner: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
        github_issues_repo: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
        github_issues_api_token: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            requiredIf(() => {
              return this.values.github_issues_api_token !== undefined
            })
          ),
        },
      },
    }
  },
}
</script>
