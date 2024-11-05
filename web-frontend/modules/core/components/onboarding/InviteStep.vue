<template>
  <div>
    <h1>{{ $t('inviteStep.title') }}</h1>
    <p>{{ $t('inviteStep.description') }}</p>

    <FormGroup
      v-for="(email, i) in emails"
      :key="i"
      :error="v$.emails.$each[i].$dirty && !v$.emails.$each[i].email"
      required
      small-label
      class="margin-bottom-2"
    >
      <template v-if="i === 0" #label
        ><span class="margin-bottom-2">{{
          $t('inviteStep.collaboratorsLabel')
        }}</span></template
      >
      <FormInput
        v-model="emails[i]"
        :label="i === 0 ? $t('inviteStep.collaboratorsLabel') : null"
        :placeholder="'example@gmail.com'"
        :error="v$.emails.$each[i].$dirty && !v$.emails.$each[i].email"
        icon-right="iconoir-mail"
        size="large"
        @input="updateValue(i, $event)"
        @blur="v$.emails.$each[i].$touch()"
      />
      <template #error>{{ $t('error.email') }}</template>
    </FormGroup>
  </div>
</template>

<script>
import { email } from '@vuelidate/validators'

export default {
  name: 'InviteStep',
  data() {
    return {
      emails: ['', '', '', '', ''],
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
      const emails = this.emails.filter((email) => !!email)
      this.$emit('update-data', { emails })
    },
  },
  validations() {
    return {
      emails: {
        $each: { email },
      },
    }
  },
}
</script>
