<template>
  <div>
    <RadioCard
      v-for="option in twoFaOptions"
      :key="option.type"
      :value="option.type"
      :model-value="values.twoFaChoice"
      :label="option.name"
      :badge-label="option.sideLabel"
      @input="updateValue"
    >
      <div>
        {{ option.description }}
      </div>
    </RadioCard>
    <div class="actions actions--right actions--gap">
      <Button type="secondary" @click="$emit('cancel')">{{
        $t('enableTwoFactorOptions.cancel')
      }}</Button>
      <Button type="primary" @click="$emit('continue', values.twoFaChoice)">{{
        $t('enableTwoFactorOptions.continue')
      }}</Button>
    </div>
  </div>
</template>

<script>
export default {
  name: 'EnableTwoFactorOptions',
  data() {
    return {
      values: {
        twoFaChoice: 'totp',
      },
    }
  },
  computed: {
    twoFaOptions() {
      return this.$registry.getList('twoFactorAuth')
    },
  },
  methods: {
    updateValue(value) {
      this.values.twoFaChoice = value
    },
  },
}
</script>
