<template functional>
  <div ref="cell" class="grid-view__cell" :class="data.staticClass || ''">
    <client-only>
      <div class="grid-field-date">
        <div ref="dateDisplay" class="grid-field-date__date">
          {{
            $options.methods.getDate(props.field, props.value) || props.value
          }}
        </div>
        <div
          v-if="props.field.date_include_time"
          ref="timeDisplay"
          class="grid-field-date__time"
        >
          {{ $options.methods.getTime(props.field, props.value) }}
        </div>
        <div
          v-if="props.field.date_show_tzinfo"
          class="grid-field-date__tzinfo"
        >
          {{ $options.methods.getCellTimezoneAbbr(props.field, props.value) }}
        </div>
      </div>
    </client-only>
  </div>
</template>

<script>
import readOnlyDateField from '@baserow/modules/database/mixins/readOnlyDateField'

export default {
  name: 'FunctionalGridViewFieldDate',
  mixins: [readOnlyDateField],
}
</script>
