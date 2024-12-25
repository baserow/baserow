<template>
  <Context ref="context" overflow-scroll max-height-if-outside-viewport>
    <ul class="context__menu timeline-timescale-context">
      <li
        v-for="(option, index) in options"
        :key="option.value"
        class="context__menu-item"
        :class="{
          'context__menu-item--with-separator': index > 0,
        }"
        @click="option.enabled ? $emit('select', option.value) : null"
      >
        <div>
          <a
            v-tooltip="
              option.enabled
                ? null
                : $t('timelineTimescaleContext.disabledTooltip')
            "
            tooltip-position="bottom-left"
            class="context__menu-item-link timeline-timescale-context__item-link"
            :class="{
              disabled: !option.enabled,
            }"
          >
            {{ $t(`timelineTimescaleContext.${option.value}`) }}
            <i
              v-if="option.value === timescale"
              class="context__menu-icon iconoir-check"
            ></i>
          </a>
        </div>
      </li>
    </ul>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'

export default {
  name: 'TimelineTimescaleContext',
  mixins: [context],
  props: {
    timescale: {
      type: String,
      required: true,
    },
    startDateField: {
      type: Object,
      required: true,
    },
  },
  computed: {
    options() {
      return [
        { value: 'year', enabled: true },
        { value: 'month', enabled: true },
        { value: 'week', enabled: true },
        { value: 'day', enabled: this.startDateField?.date_include_time },
      ]
    },
  },
  methods: {
    isOpen() {
      return this.$refs.context.isOpen()
    },
  },
}
</script>
