<template>
  <div>
    <h2 class="box__title">{{ $t('emailNotifications.title') }}</h2>
    <form @submit.prevent="updateEmailNotificationFrequency">
      <FormGroup
        :label="$t('emailNotifications.label')"
        :help-text="$t('emailNotifications.description')"
        :error="v$.email_notification_frequency.$error"
        required
      >
        <RadioGroup
          v-model="v$.email_notification_frequency.$model"
          :options="emailNotificationOptions"
          vertical-layout
        >
        </RadioGroup>
      </FormGroup>

      <div class="actions actions--right">
        <Button
          type="primary"
          size="large"
          :loading="loading"
          :disabled="submitDisabled || loading"
          icon="iconoir-bin"
        >
          {{ $t('emailNotifications.submitButton') }}
        </Button>
      </div>
    </form>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import { mapGetters } from 'vuex'
import { required } from '@vuelidate/validators'
import { EMAIL_NOTIFICATIONS_FREQUENCY_OPTIONS } from '@baserow/modules/core/enums'
import { notifyIf } from '@baserow/modules/core/utils/error'

import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'EmailNotifications',
  mixins: [form],
  data() {
    return {
      loading: false,
      allowedValues: ['email_notification_frequency'],
      values: null,
      v$: null,
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
  created() {
    const values = reactive({
      email_notification_frequency:
        EMAIL_NOTIFICATIONS_FREQUENCY_OPTIONS.INSTANT,
    })

    const rules = computed(() => ({
      email_notification_frequency: {
        required,
      },
    }))
    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
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
    async updateEmailNotificationFrequency() {
      this.loading = true
      try {
        await this.$store.dispatch('auth/update', {
          email_notification_frequency:
            this.values.email_notification_frequency,
        })
      } catch (error) {
        notifyIf(error, 'settings.')
        this.setInitialValue()
      }
      this.loading = false
    },
  },
}
</script>
