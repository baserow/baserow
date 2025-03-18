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
import { en, fr } from 'vuejs-datepicker/dist/locale'

export default {
  name: 'ViewFilterTypeDateUpgradeToMultiStep',
  mixins: [filterTypeDateInput],
  data() {
    return {
      loading: false,
      dateString: '',
      dateObject: '',
      datePickerLang: {
        en,
        fr,
      },
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
