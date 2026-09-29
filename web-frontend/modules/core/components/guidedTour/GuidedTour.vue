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
        :videos="currentStep.videos"
        :stoppable="forced"
        @previous="goto(stepIndex - 1)"
        @next="next"
        @stop="stop"
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
        .filter(() => {
          return this.authenticated
        })
        .filter((type) => {
          if (this.forced) {
            // A manually replayed tour must be shown even if it has already been
            // completed, but tours that must only be seen the first time are
            // excluded.
            return type.showOnReplay
          }
          return !this.completed.includes(type.getType())
        })
        .filter((type) => type.isActive(this.$route))
        .sort((a, b) => a.order - b.order)
    },
    started() {
      return this.activeGuidedTours.length > 0
    },
    allSteps() {
      return this.activeGuidedTours
        .flatMap((type) => type.steps)
        .filter((step) => !this.forced || step.showOnReplay)
    },
    currentStep() {
      return this.allSteps[this.stepIndex]
    },
    ...mapGetters({
      authenticated: 'auth/isAuthenticated',
      completed: 'auth/getCompletedGuidedTour',
      forced: 'guidedTour/isForced',
    }),
  },
  watch: {
    started(value) {
      // A forced start is handled by the `forced` watcher, which can't be done here
      // because the tour could already be started when it changes.
      if (value && !this.forced) {
        this.show()
      }
    },
    forced(value) {
      if (value) {
        this.stepIndex = 0
        if (this.started) {
          this.show()
        }
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
    async stop() {
      const step = this.allSteps[this.stepIndex]
      await step.afterShow()

      this.$refs.highlight.hide()
      this.stepIndex = 0
      await this.$store.dispatch('guidedTour/stop')
    },
    async finish() {
      if (this.forced) {
        // A manually restarted tour must not save the completed state because it has
        // typically already been completed, and it must be possible to restart it
        // again.
        return await this.stop()
      }

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
