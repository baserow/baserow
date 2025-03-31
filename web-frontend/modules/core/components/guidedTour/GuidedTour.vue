<template>
  <div>
    <Highlight ref="highlight" :get-parent="getParent">
      <GuidedTourStep
        v-if="currentStep"
        :step="stepIndex + 1"
        :total-steps="allSteps.length"
        :title="currentStep.title"
        :content="currentStep.content"
        :last="stepIndex >= allSteps.length - 1"
        :position="currentStep.position"
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
  mounted() {
    if (this.started) {
      this.show()
    }
  },
  methods: {
    getParent() {
      return this.$el.parentElement
    },
    async next() {
      if (this.stepIndex >= this.allSteps.length - 1) {
        return await this.finish()
      }

      this.goto(this.stepIndex + 1)
    },
    goto(index) {
      this.stepIndex = index
      this.show()
    },
    show() {
      this.$refs.highlight.show(this.allSteps[this.stepIndex].selectors)
    },
    async finish() {
      this.$refs.highlight.hide()
      this.stepIndex = 0

      try {
        // @TODO persistently save the completed onboardings.
        // const { data } = await AuthService(this.$client).update({
        //   completed_guided_tours: this.startedGuidedTours,
        // })
        const completed = this.activeGuidedTours.map((t) => t.getType())
        const data = { completed_guided_tours: completed }
        await this.$store.dispatch('auth/forceUpdateUserData', { user: data })
      } catch (error) {
        notifyIf(error)
      }
    },
  },
}
</script>
