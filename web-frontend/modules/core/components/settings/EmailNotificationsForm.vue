<template>
  <form ref="form" @submit.prevent="submit">
    <FormGroup
      :label="$t('emailNotifications.label')"
      :help-text="$t('emailNotifications.description')"
      :error="fieldHasErrors('email_notification_frequency')"
      small-label
      required
    >
      <RadioGroup
        v-model="values.email_notification_frequency"
        :options="emailNotificationOptions"
        vertical-layout
      >
      </RadioGroup>
    </FormGroup>
  </form>
</template>

<script>
import { mapGetters } from 'vuex'
import { required } from 'vuelidate/lib/validators'
import { EMAIL_NOTIFICATIONS_FREQUENCY_OPTIONS } from '@baserow/modules/core/enums'

import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'EmailNotifications',
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
  computed: {
    submitDisabled() {
      return (
        this.loading ||
        this.values.email_notification_frequency ===
          this.user.email_notification_frequency
      )
    },
    EMAIL_NOTIFICATIONS_FREQUENCY_OPTIONS() {
      return EMAIL_NOTIFICATIONS_FREQUENCY_OPTIONS
    },
    emailNotificationOptions() {
      return [
        {
          label: this.$t('emailNotifications.instant'),
          value: EMAIL_NOTIFICATIONS_FREQUENCY_OPTIONS.INSTANT,
        },
        {
          label: this.$t('emailNotifications.daily'),
          value: EMAIL_NOTIFICATIONS_FREQUENCY_OPTIONS.DAILY,
        },
        {
          label: this.$t('emailNotifications.weekly'),
          value: EMAIL_NOTIFICATIONS_FREQUENCY_OPTIONS.WEEKLY,
        },
        {
          label: this.$t('emailNotifications.never'),
          value: EMAIL_NOTIFICATIONS_FREQUENCY_OPTIONS.NEVER,
        },
      ]
    },
    ...mapGetters({
      user: 'auth/getUserObject',
    }),
  },
  mounted() {
    this.setInitialValue()
  },
  methods: {
    setInitialValue() {
      const emailNotificationFreq = this.user.email_notification_frequency
      if (emailNotificationFreq) {
        this.values.email_notification_frequency = emailNotificationFreq
      }
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
