<template>
  <EmailNotificationsForm
    ref="form"
    @submitted="submitted"
  ></EmailNotificationsForm>
</template>

<script>
import { required } from 'vuelidate/lib/validators'
import { EMAIL_NOTIFICATIONS_FREQUENCY_OPTIONS } from '@baserow/modules/core/enums'
import { notifyIf } from '@baserow/modules/core/utils/error'
import EmailNotificationsForm from '@baserow/modules/core/components/settings/EmailNotificationsForm'

import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'EmailNotificationsSettings',
  components: { EmailNotificationsForm },
  mixins: [form],
  data() {
    return {
      allowedValues: ['email_notification_frequency'],
      values: {
        email_notification_frequency:
          EMAIL_NOTIFICATIONS_FREQUENCY_OPTIONS.INSTANT,
      },
    }
  },

  methods: {
    submitForm() {
      this.$refs.form.submit()
    },
    getCTALabel() {
      return this.$t('emailNotifications.submitButton')
    },
    async submitted(values) {
      this.$emit('loading', true)
      try {
        await this.$store.dispatch('auth/update', {
          email_notification_frequency: values.email_notification_frequency,
        })
      } catch (error) {
        notifyIf(error, 'settings.')
        this.setInitialValue()
      }
      this.$emit('loading', false)
    },
  },
  validations: {
    values: {
      email_notification_frequency: {
        required,
      },
    },
  },
}
</script>
