<template>
  <Button
    v-tooltip="$t('ViewFilterTypeDateUpgradeToMultiStep.migrateButtonTooltip')"
    type="secondary"
    :loading="loading"
    :disabled="loading || disabled"
    tag="a"
    @click="$emit('migrate', migrateToNewMultiStepDateFilter())"
    >{{ $t('ViewFilterTypeDateUpgradeToMultiStep.migrateButtonText') }}
  </Button>
</template>

<script>
import filterTypeDateInput from '@baserow/modules/database/mixins/filterTypeDateInput'

export default {
  name: 'ViewFilterTypeDateUpgradeToMultiStep',
  mixins: [filterTypeDateInput],
  emits: ['migrate'],
  setup: filterTypeDateInput.setup,
  data() {
    return {
      loading: false,
      dateString: '',
      dateObject: '',
    }
  },
  mounted() {
    this.v$.$touch()
  },
  methods: {
    migrateToNewMultiStepDateFilter() {
      this.loading = true
      return this.filterType.migrateToNewMultiStepDateFilter(
        this.prepareValue(this.copy)
      )
    },
    focus() {},
  },
}
</script>
