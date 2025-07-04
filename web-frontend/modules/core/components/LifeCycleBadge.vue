<template>
  <Badge
    v-tooltip="tooltip"
    tooltip-position="bottom-right"
    :color="color"
    size="small"
    >{{ label }} <i class="iconoir-hammer"></i
  ></Badge>
</template>

<script>
export default {
  name: 'LifeCycleBadge',
  props: {
    /**
     * The application type's development stage, used to determine
     * the badge's appearance and label.
     */
    stage: {
      type: String,
      required: true,
      validator: function (value) {
        return ['alpha', 'beta'].includes(value)
      },
    },
  },
  computed: {
    color() {
      switch (this.stage) {
        case 'alpha':
          return 'magenta'
        default:
          return 'cyan'
      }
    },
    label() {
      return this.$t(`common.${this.stage}`)
    },
    tooltip() {
      switch (this.stage) {
        case 'alpha':
          return this.$t('lifeCycleBadge.alphaTooltip')
        default:
          return null
      }
    },
  },
}
</script>
