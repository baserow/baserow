<template>
  <div class="view-date-selector">
    <a class="view-date-selector__prev" @click="selectPrevious">
      <i class="iconoir-nav-arrow-left"></i>
    </a>
    <a class="view-date-selector__next" @click="selectNext">
      <i class="iconoir-nav-arrow-right"></i>
    </a>

    <Button type="secondary" size="large" @click="selectToday">
      {{ $t('viewDateSelector.today') }}
    </Button>
  </div>
</template>

<script>
import moment from '@baserow/modules/core/moment'

export default {
  name: 'ViewDateSelector',
  props: {
    selectedDate: {
      type: Object, // a moment object
      required: true,
    },
    unit: {
      type: String,
      default: 'day',
    },
  },
  methods: {
    selectPrevious() {
      const newSelectedDate = moment(this.selectedDate).subtract(1, this.unit)
      this.$emit('date-selected', newSelectedDate.startOf(this.unit))
    },
    selectToday() {
      // use the same timezone as the selected date
      const now = moment().utcOffset(this.selectedDate.utcOffset())
      this.$emit('date-selected', now.startOf(this.unit))
    },
    selectNext() {
      const newSelectedDate = moment(this.selectedDate).add(1, this.unit)
      this.$emit('date-selected', newSelectedDate.startOf(this.unit))
    },
  },
}
</script>
