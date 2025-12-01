<template>
  <i
    v-tooltip:[tooltipOptions]="tooltipText"
    class="help-icon"
    :class="iconClass"
  >
  </i>
</template>

<script>
import Markdown from 'markdown-it'

const TooltipContentPlain = 'plain'
const TooltipContentMarkdown = 'markdown'

export default {
  name: 'HelpIcon',
  props: {
    tooltip: {
      type: String,
      required: false,
      default: null,
    },
    /**
     * How many seconds the tooltip should be displayed after mouse moves out of icon/contents?
     * */
    tooltipDuration: {
      type: Number,
      required: false,
      default: 0,
    },
    /**
     *  Hints on tooltip content type.
     *  Possible values are: `plain` | `markdown`
     * */
    tooltipContentType: {
      type: String,
      required: false,
      default: TooltipContentPlain,
      validators: (contentType) => {
        return [TooltipContentMarkdown, TooltipContentPlain].includes(
          contentType
        )
      },
    },
    /**
     * Iconoir icon name without iconoir- prefix.
     * */
    icon: {
      type: String,
      required: false,
      default: 'chat-bubble-question',
    },
    /**
     * Additional css classes for tooltip icon
     * */
    tooltipClasses: {
      type: String,
      required: false,
      default: '',
    },
    /**
     * Additional css classes for tooltip content container
     * */
    tooltipContentClasses: {
      type: [Array, String],
      required: false,
      default: () => [],
    },
  },
  computed: {
    tooltipOptions() {
      return {
        duration: this.tooltipDuration,
        contentIsHtml: this.tooltipContentIsHtml(),
        contentClasses: this.tooltipContentClasses,
      }
    },
    tooltipText() {
      if (this.tooltipContentType === TooltipContentMarkdown) {
        const md = new Markdown({ html: false })
        return md.render(this.tooltip)
      }
      return this.tooltip
    },
    iconClass() {
      const clsNames = this.tooltipClasses ? [this.tooltipClasses] : []
      if (this.icon) {
        clsNames.push(`iconoir-${this.icon}`)
      }
      return clsNames.join(' ')
    },
  },
  methods: {
    tooltipContentIsHtml() {
      // tooltip directive doesn't need to know anything about markdown conversion,
      // just whether the content is html or not
      return this.tooltipContentType !== 'plain'
    },
  },
}
</script>
