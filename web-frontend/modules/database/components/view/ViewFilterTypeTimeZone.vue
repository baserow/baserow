<template>
  <div class="filters__value-timezone">{{ getTimezoneAbbr() }}</div>
</template>

<script>
import filterTypeDateInput from '@baserow/modules/database/mixins/filterTypeDateInput'

export default {
  name: 'ViewFilterTypeTimeZone',
  mixins: [filterTypeDateInput],
  setup: filterTypeDateInput.setup,
}
</script>
