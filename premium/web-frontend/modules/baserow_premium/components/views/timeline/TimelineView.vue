<template>
  <div class="timeline-view">
    <div v-if="!dateSettingsAreValid && canChangeDateSettings">
      <TimelineDateSettingsInitBox
        :fields="fields"
        :view="view"
        :read-only="readOnly"
      />
    </div>
    <TimelineContainer
      v-else
      :fields="fields"
      :view="view"
      :table="table"
      :database="database"
      :read-only="readOnly"
      :store-prefix="storePrefix"
      @selected-row="$emit('selected-row', $event)"
      @refresh="$emit('refresh', $event)"
      @navigate-previous="$emit('navigate-previous', $event)"
      @navigate-next="$emit('navigate-next', $event)"
    />
  </div>
</template>
<script>
import viewHelpers from '@baserow/modules/database/mixins/viewHelpers'
import TimelineDateSettingsInitBox from '@baserow_premium/components/views/timeline/TimelineDateSettingsInitBox'
import TimelineContainer from '@baserow_premium/components/views/timeline/TimelineContainer.vue'
import timelineViewHelpers from '@baserow_premium/mixins/timelineViewHelpers'

export default {
  name: 'TimelineView',
  components: { TimelineDateSettingsInitBox, TimelineContainer },
  mixins: [viewHelpers, timelineViewHelpers],
  props: {
    loading: {
      type: Boolean,
      required: true,
    },
  },
  watch: {
    dateSettingsAreValid: {
      // Refetch rows when the date settings become valid.
      handler(newVal, oldVal) {
        if (newVal && !oldVal) {
          this.$emit('refresh', {
            includeFieldOptions: true,
          })
        }
      },
    },
  },
}
</script>
