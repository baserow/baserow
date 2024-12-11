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
        :disabled="disabled"
        @focus.once="$event.target.select()"
        @blur="$v.values.gitlab_url.$touch()"
      />
      <template #error>
        <span
          v-if="$v.values.gitlab_url.$dirty && !$v.values.gitlab_url.required"
        >
          {{ $t('error.requiredField') }}
        </span>
        <span
          v-else-if="$v.values.gitlab_url.$dirty && !$v.values.gitlab_url.url"
        >
          {{ $t('error.invalidURL') }}
        </span>
      </template>
    </FormGroup>

    <FormGroup
      :error="fieldHasErrors('gitlab_project_id')"
      :label="$t('gitlabIssuesDataSync.projectId')"
      required
      class="margin-bottom-2"
      :helper-text="$t('gitlabIssuesDataSync.projectIdHelper')"
      small-label
    >
      <FormInput
        v-model="values.gitlab_project_id"
        :error="fieldHasErrors('gitlab_project_id')"
        :disabled="disabled"
        size="large"
        @blur="$v.values.gitlab_project_id.$touch()"
      />
      <template #error>
        <span
          v-if="
            $v.values.gitlab_project_id.$dirty &&
            !$v.values.gitlab_project_id.required
          "
        >
          {{ $t('error.requiredField') }}
        </span>
      </template>
    </FormGroup>

    <FormGroup
      :error="fieldHasErrors('gitlab_access_token')"
      :label="$t('gitlabIssuesDataSync.accessToken')"
      required
      class="margin-bottom-2"
      :helper-text="$t('gitlabIssuesDataSync.accessTokenHelper')"
      small-label
      :protected-edit="update"
      @enabled-protected-edit="allowedValues.push('gitlab_access_token')"
      @disable-protected-edit="
        ;[
          allowedValues.splice(allowedValues.indexOf('gitlab_access_token'), 1),
          delete values['gitlab_access_token'],
        ]
      "
    >
      <FormInput
        v-model="values.gitlab_access_token"
        :error="fieldHasErrors('gitlab_access_token')"
        :disabled="disabled"
        size="large"
        @blur="$v.values.gitlab_access_token.$touch()"
      />
      <template #error>
        <span
          v-if="
            $v.values.gitlab_access_token.$dirty &&
            !$v.values.gitlab_access_token.required
          "
        >
          {{ $t('error.requiredField') }}
        </span>
      </template>
    </FormGroup>
  </form>
</template>

<script>
import { required, requiredIf, url } from 'vuelidate/lib/validators'
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'GitLabIssuesDataSyncForm',
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
    const allowedValues = ['gitlab_url', 'gitlab_project_id']
    if (!this.update) {
      allowedValues.push('gitlab_access_token')
    }
    return {
      allowedValues,
      values: {
        gitlab_url: 'https://gitlab.com',
        gitlab_project_id: '',
      },
    }
  },
  validations() {
    return {
      values: {
        gitlab_url: { required, url },
        gitlab_project_id: { required },
        gitlab_access_token: {
          required: requiredIf(() => {
            return this.allowedValues.includes('gitlab_access_token')
          }),
        },
      },
    }
  },
}
</script>
