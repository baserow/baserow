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
        v-model="values.github_issues_owner"
        :error="fieldHasErrors('github_issues_owner')"
        :disabled="disabled"
        size="large"
        @blur="$v.values.github_issues_owner.$touch()"
      />
      <template #error>
        <span
          v-if="
            $v.values.github_issues_owner.$dirty &&
            !$v.values.github_issues_owner.required
          "
        >
          {{ $t('error.requiredField') }}
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
        v-model="values.github_issues_repo"
        :error="fieldHasErrors('github_issues_repo')"
        :disabled="disabled"
        size="large"
        @blur="$v.values.github_issues_repo.$touch()"
      />
      <template #error>
        <span
          v-if="
            $v.values.github_issues_owner.$dirty &&
            !$v.values.github_issues_owner.required
          "
        >
          {{ $t('error.requiredField') }}
        </span>
      </template>
    </FormGroup>

    <FormGroup
      :error="fieldHasErrors('github_issues_api_token')"
      :label="$t('githubIssuesDataSync.apiToken')"
      required
      :helper-text="$t('githubIssuesDataSync.apiTokenHelper')"
      small-label
      :protected-edit="update"
      @enabled-protected-edit="allowedValues.push('github_issues_api_token')"
      @disable-protected-edit="
        ;[
          allowedValues.splice(
            allowedValues.indexOf('github_issues_api_token'),
            1
          ),
          delete values['github_issues_api_token'],
        ]
      "
    >
      <FormInput
        v-model="values.github_issues_api_token"
        :error="fieldHasErrors('github_issues_api_token')"
        :disabled="disabled"
        size="large"
        @blur="$v.values.github_issues_api_token.$touch()"
      />
      <template #error>
        <span
          v-if="
            $v.values.github_issues_api_token.$dirty &&
            !$v.values.github_issues_api_token.required
          "
        >
          {{ $t('error.requiredField') }}
        </span>
      </template>
    </FormGroup>
  </form>
</template>

<script>
import { required, requiredIf } from 'vuelidate/lib/validators'
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
  data() {
    const allowedValues = ['github_issues_owner', 'github_issues_repo']
    if (!this.update) {
      allowedValues.push('github_issues_api_token')
    }
    return {
      allowedValues: ['github_issues_owner', 'github_issues_repo'],
      values: {
        github_issues_owner: '',
        github_issues_repo: '',
      },
    }
  },
  validations() {
    return {
      values: {
        github_issues_owner: { required },
        github_issues_repo: { required },
        github_issues_api_token: {
          required: requiredIf(() => {
            return this.allowedValues.includes('github_issues_api_token')
          }),
        },
      },
    }
  },
}
</script>
