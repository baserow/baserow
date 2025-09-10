<template>
  <div>
    <RadioGroup
      v-model="values.twoFaChoice"
      :options="twoFaOptions"
      vertical-layout
    >
    </RadioGroup>
    <Button type="secondary" @click="$emit('cancel')">Cancel</Button>
    <Button type="primary" @click="$emit('continue')">Continue</Button>
  </div>
</template>

<script>
export default {
  name: 'EnableTwoFactorOptions',
  data() {
    return {
      values: {
        twoFaChoice: 'authapp',
      },
    }
  },
  computed: {
    twoFaOptions() {
      return [
        {
          label: 'Authentication app', // TODO: this.$t('twoFac.instant'),
          value: 'authapp', // EMAIL_NOTIFICATIONS_FREQUENCY_OPTIONS.INSTANT,
        },
        {
          label: 'Email', // this.$t('emailNotifications.daily'),
          value: 'email', // EMAIL_NOTIFICATIONS_FREQUENCY_OPTIONS.DAILY,
        },
      ]
    },
  },
}
</script>
