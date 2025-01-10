<template>
  <div>
    <h1>{{ $t('inviteStep.title') }}</h1>
    <p>{{ $t('inviteStep.description') }}</p>

    <FormGroup
      v-for="(email, index) in emails"
      :key="index"
      :error="v$.emails.$each.$response?.$data[index]?.email.$error"
      required
      small-label
      class="margin-bottom-2"
    >
      <template v-if="index === 0" #label
        ><span class="margin-bottom-2">{{
          $t('inviteStep.collaboratorsLabel')
        }}</span></template
      >
      <FormInput
        v-model="email.email"
        :label="index === 0 ? $t('inviteStep.collaboratorsLabel') : null"
        :placeholder="'example@gmail.com'"
        :error="v$.emails.$each.$response?.$data[index]?.email.$error"
        icon-right="iconoir-mail"
        size="large"
        @input="updateValue(index, $event)"
        @blur="v$.emails.$touch"
      />
      <template #error>{{ $t('error.email') }}</template>
    </FormGroup>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { reactive } from 'vue'
import { email, helpers } from '@vuelidate/validators'

export default {
  name: 'InviteStep',
  setup() {
    const values = reactive({
      emails: [
        { email: '' },
        { email: '' },
        { email: '' },
        { email: '' },
        { email: '' },
      ],
    })

    const rules = {
      emails: {
        $each: helpers.forEach({ email: { email } }),
      },
    }

    return {
      emails: values.emails,
      v$: useVuelidate(rules, values, { $lazy: true }),
    }
  },
  mounted() {
    this.updateValue()
  },
  methods: {
    isValid() {
      return !this.v$.$invalid
    },
    updateValue() {
      const filteredEmails = this.emails.filter((email) => !!email.email)
      const emails = filteredEmails.map((email) => email.email)
      console.log(emails)
      this.$emit('update-data', { emails })
    },
  },
}
</script>
