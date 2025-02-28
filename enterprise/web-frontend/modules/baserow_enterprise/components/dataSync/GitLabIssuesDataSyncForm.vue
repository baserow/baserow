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
        v-model="v$.values.gitlab_url.$model"
        size="large"
        :error="fieldHasErrors('gitlab_url')"
        :disabled="disabled"
        @focus.once="$event.target.select()"
        @blur="v$.values.gitlab_url.$touch"
      />
      <template #error>
        {{ v$.values.gitlab_url.$errors[0]?.$message }}
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
        v-model="v$.values.gitlab_project_id.$model"
        :error="fieldHasErrors('gitlab_project_id')"
        :disabled="disabled"
        size="large"
        @blur="v$.values.gitlab_project_id.$touch"
      />
      <template #error>
        {{ v$.values.gitlab_project_id.$errors[0]?.$message }}
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
      @enabled-protected-edit="values.gitlab_access_token = ''"
      @disable-protected-edit="values.gitlab_access_token = undefined"
    >
      <FormInput
        v-model="v$.values.gitlab_access_token.$model"
        :error="fieldHasErrors('gitlab_access_token')"
        :disabled="disabled"
        size="large"
        @blur="v$.values.gitlab_access_token.$touch"
      />
      <template #error>
        {{ v$.values.gitlab_access_token.$errors[0]?.$message }}
      </template>
    </FormGroup>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required, requiredIf, url, helpers } from '@vuelidate/validators'
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
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    const allowedValues = [
      'gitlab_url',
      'gitlab_project_id',
      'gitlab_access_token',
    ]
    return {
      allowedValues,
      values: {
        gitlab_url: 'https://gitlab.com',
        gitlab_project_id: '',
        gitlab_access_token: this.update ? undefined : '',
      },
    }
  },
  validations() {
    return {
      values: {
        gitlab_url: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          url: helpers.withMessage(this.$t('error.invalidURL'), url),
        },
        gitlab_project_id: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
        gitlab_access_token: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            requiredIf(() => {
              return this.values.gitlab_access_token !== undefined
            })
          ),
        },
      },
    }
  },
}
</script>
