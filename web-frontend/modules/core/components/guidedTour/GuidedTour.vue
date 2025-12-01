<template>
  <div
    v-if="activeGuidedTours.length > 0"
    class="guided-tour-step__container"
    @click.stop
  >
    <Highlight
      ref="highlight"
      :get-parent="getParent"
      :padding="currentStep.highlightPadding ?? 2"
    >
      <GuidedTourStep
        v-if="currentStep"
        :step="stepIndex + 1"
        :total-steps="allSteps.length"
        :title="currentStep.title"
        :content="currentStep.content"
        :first="stepIndex === 0"
        :last="stepIndex >= allSteps.length - 1"
        :position="currentStep.position"
        :button-text="currentStep.buttonText"
        @previous="goto(stepIndex - 1)"
        @next="next"
      ></GuidedTourStep>
    </Highlight>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import Highlight from '@baserow/modules/core/components/Highlight'
import GuidedTourStep from '@baserow/modules/core/components/guidedTour/GuidedTourStep'
import AuthService from '@baserow/modules/core/services/auth'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'GuidedTour',
  components: { Highlight, GuidedTourStep },
  data() {
    return {
      stepIndex: 0,
    }
  },
  computed: {
    activeGuidedTours() {
      return Object.values(this.$registry.getAll('guidedTour'))
        .filter((type) => {
          return !this.completed.includes(type.getType())
        })
        .filter((type) => type.isActive(this.$route))
        .sort((a, b) => a.order - b.order)
    },
    started() {
      return this.activeGuidedTours.length > 0
    },
    allSteps() {
      return this.activeGuidedTours.flatMap((type) => type.steps)
    },
    currentStep() {
      return this.allSteps[this.stepIndex]
    },
    ...mapGetters({
      completed: 'auth/getCompletedGuidedTour',
    }),
  },
  watch: {
    started(value) {
      if (value) {
        this.show()
      }
    },
    activeGuidedTours(value) {
      if (this.stepIndex > value.length) {
        this.goto(value.length)
      }
    },
  },
  mounted() {
    if (this.started) {
      this.show()
    }
  },
  methods: {
    getParent() {
      return document.body
    },
    async next() {
      if (this.stepIndex >= this.allSteps.length - 1) {
        return await this.finish()
      }

      await this.goto(this.stepIndex + 1)
    },
    async goto(index) {
      const step = this.allSteps[this.stepIndex]
      await step.afterShow()

      this.stepIndex = index
      this.show()
    },
    async show() {
      const step = this.allSteps[this.stepIndex]
      await this.$nextTick()
      await step.beforeShow(this.getParent())
      await this.$nextTick()
      this.$refs.highlight.show(step.selectors)
    },
    async finish() {
      const step = this.allSteps[this.stepIndex]
      await step.afterShow()

      this.$refs.highlight.hide()
      this.stepIndex = 0

      try {
        const completed = this.activeGuidedTours
          .filter((t) => t.saveCompleted)
          .map((t) => t.getType())
        const { data } = await AuthService(this.$client).update({
          completed_guided_tours: completed,
        })
        await this.$store.dispatch('auth/forceUpdateUserData', { user: data })
      } catch (error) {
        notifyIf(error)
      }

      for (const tour of Object.values(this.activeGuidedTours)) {
        await tour.completed()
      }
    },
  },
}
</script>
