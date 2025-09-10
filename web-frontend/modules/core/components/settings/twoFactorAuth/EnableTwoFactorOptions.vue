<template>
  <div>
    <!-- <RadioGroup
      v-model="values.twoFaChoice"
      :options="twoFaOptions"
      vertical-layout
    > -->
    <!-- </RadioGroup> -->
    <RadioCard
      :value="'authapp'"
      :model-value="values.twoFaChoice"
      :side-label="'Recommended'"
      @input="updateValue"
    >
      <div>
        Use an app to get two-factor authentication codes. We recommend using
        apps such as Google Authenticator, Authy and Microsoft Authenticator.
      </div>
    </RadioCard>
    <div>&nbsp;</div>
    <RadioCard
      :value="'email'"
      :model-value="values.twoFaChoice"
      @input="updateValue"
    >
      <div>Baserow will send a temporary login link via email.</div>
    </RadioCard>
    <div>&nbsp;</div>
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
  methods: {
    updateValue(value) {
      this.values.twoFaChoice = value
    },
  },
}
</script>
