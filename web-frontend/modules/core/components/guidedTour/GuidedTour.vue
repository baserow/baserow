<template>
  <div>
    <Highlight ref="highlight" :get-parent="getParent">
      <GuidedTourStep
        v-if="currentStep"
        :step="stepIndex + 1"
        :total-steps="allSteps.length"
        :title="currentStep.title"
        :content="currentStep.content"
        :last="stepIndex === allSteps.length"
        :position="currentStep.position"
      ></GuidedTourStep>
    </Highlight>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import Highlight from '@baserow/modules/core/components/Highlight'
import GuidedTourStep from '@baserow/modules/core/components/guidedTour/GuidedTourStep'

export default {
  name: 'GuidedTour',
  components: { Highlight, GuidedTourStep },
  data() {
    return {
      stepIndex: 0,
      started: false,
      startedGuidedTours: [],
    }
  },
  computed: {
    startedGuidedTourTypes() {
      return this.startedGuidedTours
        .map((type) => {
          return this.$registry.get('guidedTour', type)
        })
        .sort((a, b) => a.order - b.order)
    },
    allSteps() {
      return this.startedGuidedTourTypes.flatMap((type) => type.steps)
    },
    currentStep() {
      return this.allSteps[this.stepIndex]
    },
    ...mapGetters({
      completed: 'auth/getCompletedGuidedTour',
    }),
  },
  mounted() {
    this.$bus.$on('add-guided-tour', this.addGuidedTour)
  },
  methods: {
    getParent() {
      return this.$el.parentElement
    },
    start() {
      this.started = true
      this.$nextTick(() => {
        console.log(this.allSteps)
        // debugger
        this.$refs.highlight.show([
          `[data-highlight="workspaces"]`,
          `[data-highlight="menu"]`,
        ])
      })
    },
    addGuidedTour(type) {
      if (!this.completed.includes(type)) {
        this.startedGuidedTours.push(type)
        this.start()
      }
    },
  },
}
</script>
