<template>
  <div>
    <h2>
      {{ $t('emailTester.title') }}

      <a
        href="https://baserow.io/docs/installation%2Fconfiguration#email-configuration"
        target="_blank"
        ><i class="iconoir-chat-bubble-question"
      /></a>
    </h2>
    <Error :error="error" />
    <div v-if="testResult.succeeded != null">
      <Alert v-if="!testResult.succeeded" type="error">
        <template #title>{{ testResult.error_type }}</template>
        <div>
          <p>{{ testResult.error }}</p>
          <pre class="email-tester__full-stack">{{ trimmedFullStack }}</pre>
        </div>
      </Alert>
      <Alert v-else type="success">
        <template #title>{{ $t('emailTester.success') }}</template>
      </Alert>
    </div>
    <form @submit.prevent="submit">
      <FormGroup
        v-if="v$.values.targetEmail"
        required
        small-label
        class="margin-bottom-2"
        :label="$t('emailTester.targetEmailLabel')"
        :error="fieldHasErrors('targetEmail')"
      >
        <FormInput
          ref="name"
          v-model="v$.values.targetEmail.$model"
          :error="fieldHasErrors('targetEmail')"
          :disabled="loading"
          @blur="v$.values.targetEmail.$touch"
        ></FormInput>

        <template #error>
          {{ v$.values.targetEmail.$errors[0]?.$message }}
        </template>
      </FormGroup>

      <Button :loading="loading" :disabled="loading || v$.$invalid">
        {{ $t('emailTester.submit') }}
      </Button>
    </form>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'

import { reactive, getCurrentInstance } from 'vue'
import error from '@baserow/modules/core/mixins/error'
import HealthService from '@baserow/modules/core/services/health'
import form from '@baserow/modules/core/mixins/form'
import { required, email, helpers } from '@vuelidate/validators'
import { mapGetters } from 'vuex'
export default {
  name: 'EmailerTester',
  mixins: [error, form],
  setup() {
    const instance = getCurrentInstance()
    const values = reactive({
      targetEmail: 'test@example.com',
    })

    const rules = {
      values: {
        targetEmail: {
          required: helpers.withMessage(
            instance.proxy.$t('error.requiredField'),
            required
          ),
          email: helpers.withMessage(
            instance.proxy.$t('emailTester.invalidTargetEmail'),
            email
          ),
        },
      },
    }

    const v$ = useVuelidate(rules, { values }, { $lazy: true })

    return { values, v$, loading: false }
  },
  data() {
    return {
      testResult: {
        succeeded: null,
        error_type: null,
        error: null,
        error_stack: null,
      },
    }
  },
  computed: {
    ...mapGetters({ username: 'auth/getUsername' }),
    trimmedFullStack() {
      return this.testResult?.error_stack?.trim()
    },
  },
  mounted() {
    if (this.username) {
      this.values.targetEmail = this.username
    }
  },
  methods: {
    async submit() {
      this.loading = true
      this.testResult = {}
      this.hideError()

      try {
        const { data } = await HealthService(this.$client).testEmail(
          this.values.targetEmail
        )
        this.testResult = data
      } catch (e) {
        this.handleError(e, 'health')
        this.testResult = {}
      }

      this.loading = false
    },
  },
}
</script>
