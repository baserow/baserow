<template>
  <div :class="`guided-tour-step guided-tour-step--${position}`">
    <div v-auto-overflow-scroll class="guided-tour-step__body">
      <div class="guided-tour-step__page">
        {{ $t('guidedTourStep.step', { step, totalSteps }) }}
      </div>
      <div class="guided-tour-step__title">
        {{ title }}
      </div>
      <div class="guided-tour-step__description">
        <MarkdownIt :content="content" />
      </div>
    </div>
    <div class="guided-tour-step__foot">
      <div class="flex justify-content-space-between align-items-center">
        <a
          v-if="!first"
          href="#"
          class="guided-tour-step__back"
          @click="$emit('previous')"
          >{{ $t('guidedTourStep.back') }}</a
        >
        <Button type="secondary" @click="$emit('next')">{{
          buttonText ||
          (last ? $t('guidedTourStep.gotIt') : $t('guidedTourStep.next'))
        }}</Button>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'GuidedTourStep',
  props: {
    position: {
      required: true,
      type: String,
      validator(value) {
        return [
          'right-top',
          'right-bottom',
          'left-top',
          'bottom-left',
          'bottom-right',
          'bottom-center',
          'center',
        ].includes(value)
      },
    },
    step: {
      type: Number,
      required: true,
    },
    totalSteps: {
      type: Number,
      required: true,
    },
    title: {
      type: String,
      required: true,
    },
    content: {
      type: String,
      required: true,
    },
    first: {
      type: Boolean,
      required: false,
      default: false,
    },
    last: {
      type: Boolean,
      required: false,
      default: false,
    },
    buttonText: {
      validator: (prop) => typeof prop === 'string' || prop === null,
      required: false,
      default: null,
    },
  },
  async mounted() {
    const updatePosition = () => {
      const rect = this.$el.getBoundingClientRect()
      this.$el.style['max-height'] = `calc(100vh - ${rect.top - 12}px)`
    }

    // Delay the position update to the next tick to let the Context content
    // be available in DOM for accurate positioning.
    await this.$nextTick()
    updatePosition()

    this.$el.updatePositionViaResizeEvent = () => {
      updatePosition()
    }
    window.addEventListener('resize', this.$el.updatePositionViaResizeEvent)
  },
  beforeDestroy() {
    window.removeEventListener(
      'scroll',
      this.$el.updatePositionViaScrollEvent,
      true
    )
    window.removeEventListener('resize', this.$el.updatePositionViaResizeEvent)
  },
}
</script>
