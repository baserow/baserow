<template>
  <div class="onboarding">
    <Toasts></Toasts>
    <div v-if="creating && creatingFailed" class="onboarding__loading">
      <div class="onboarding__loading-text">
        {{ $t('onboarding.failedTitle') }}
      </div>
      <p>
        {{ $t('onboarding.failedDescription') }}
      </p>
      <div>
        <Button
          type="secondary"
          size="large"
          :loading="reloading"
          @click="refresh()"
          >{{ $t('onboarding.failedTryAgain') }}</Button
        >
        <Button
          type="danger"
          size="large"
          :loading="cancelling"
          @click="cancel"
          >{{ $t('onboarding.failedSkip') }}</Button
        >
      </div>
    </div>
    <div v-else-if="creating" class="onboarding__loading">
      <div class="loading"></div>
      <div class="onboarding__loading-text">
        {{ $t('onboarding.creating') }}
      </div>
      <div v-if="job" class="onboarding__loading-progress">
        <ProgressBar :value="job.progress_percentage" />
      </div>
    </div>
    <template v-else>
      <div class="onboarding__form">
        <div class="onboarding__head">
          <Logo class="onboarding__logo" />
          <CircleProgressBar :value="progressPercentage"></CircleProgressBar>
        </div>
        <div ref="bodyWrapper" class="onboarding__body-wrapper">
          <div class="onboarding__body">
            <div>
              <component
                :is="step.getFormComponent()"
                ref="form"
                :data="data"
                @update-data="updateData"
              ></component>
            </div>
            <div class="onboarding__actions">
              <Button
                :ph-autocapture="'onboarding-continue-step-' + step.getType()"
                type="primary"
                size="large"
                full-width
                :disabled="!isValid() || !data"
                @click="next()"
                >{{ $t('onboarding.continue') }}</Button
              >
              <div v-if="canSkip" class="onboarding__skip">
                <ButtonText
                  :ph-autocapture="'onboarding-skip-step-' + step.getType()"
                  tag="a"
                  @click="skip"
                  >{{ $t('onboarding.skip') }}</ButtonText
                >
              </div>
            </div>
          </div>
        </div>
        <div v-if="stepIndex === 0" class="onboarding__cancel">
          <ButtonText
            :ph-autocapture="'onboarding-cancel-step-' + step.getType()"
            tag="a"
            :loading="cancelling"
            @click="cancel"
            >{{ $t('onboarding.cancel') }}</ButtonText
          >
        </div>
      </div>
      <div class="onboarding__preview">
        <component
          :is="step.getPreviewComponent(data)"
          v-bind="step.getAdditionalPreviewProps()"
          :data="data"
        ></component>
      </div>
    </template>
  </div>
</template>

<script>
import CircleProgressBar from '@baserow/modules/core/components/CircleProgressBar.vue'
import { notifyIf } from '@baserow/modules/core/utils/error'
import Toasts from '@baserow/modules/core/components/toasts/Toasts'
import AuthService from '@baserow/modules/core/services/auth'
import WorkspaceService from '@baserow/modules/core/services/workspace'
import error from '@baserow/modules/core/mixins/error'
import jobProgress from '@baserow/modules/core/mixins/jobProgress'

export default {
  components: { Toasts, CircleProgressBar },
  mixins: [error, jobProgress],
  middleware: ['settings', 'authenticated'],
  asyncData({ store, redirect }) {
    // If the user has completed the onboarding, then redirect to the on-boarding page
    // so that the user can create their first one.
    const user = store.getters['auth/getUserObject']
    if (user.completed_onboarding) {
      return redirect({ name: 'dashboard' })
    }
  },
  data() {
    return {
      stepIndex: 0,
      data: {},
      creating: false,
      creatingFailed: false,
      cancelling: false,
      reloading: false,
    }
  },
  head() {
    return {
      title: this.$t('onboarding.title'),
    }
  },
  computed: {
    steps() {
      const steps = Object.values(this.$registry.getAll('onboarding'))
      return steps
        .filter((step) => {
          return step.condition(this.data)
        })
        .sort((a, b) => a.getOrder() - b.getOrder())
    },
    step() {
      return this.steps[this.stepIndex]
    },
    progressPercentage() {
      return Math.ceil((this.stepIndex / this.steps.length) * 100)
    },
    canSkip() {
      return this.step.canSkip()
    },
  },
  methods: {
    /**
     * Called when the user wants to go to the user step. This means that the provided
     * form values must be valid. If the onboarding reached the end, it should
     * automatically complete it.
     */
    async next() {
      if (this.stepIndex === this.steps.length - 1) {
        await this.complete()
      } else {
        this.stepIndex++
        this.$nextTick(() => {
          this.$refs.bodyWrapper.scrollTop = 0
        })
      }
    },
    /**
     * Called when the user wants to skip a step. It's not possible to this for every
     * step.
     */
    async skip() {
      // If the step is skipped, we don't want to store any left over data of the form
      // because that can influence what happens when completing.
      delete this.data[this.step.getType()]
      await this.next()
    },
    /**
     * Called when all the steps have been filled out. It will start the process off
     * completing the onboarding by collecting the data filled out by every step, and
     * call the `complete` method of every step. This will make sure that the onboarding
     * only creating the appropriate resources if every step has been completed
     * successfully.
     */
    async complete() {
      this.creating = true
      const responses = {}
      let route = { name: 'dashboard' }

      // Now that all the steps have been completed, we're looping over all of them and
      // execute the `complete` method to actually create the configured workspace.
      for (let i = 0; i < this.steps.length; i++) {
        const step = this.steps[i]
        try {
          responses[step.getType()] = await step.complete(this.data, responses)
        } catch (error) {
          // Stop the creating process if any of the steps fail.
          this.creatingFailed = true
          return
        }
        // Check if there is a job that must be polled after completion. If so, it will
        // show a progressbar to the user, and it will set the job end result as
        // response for this onboarding step.
        const job = step.getJobForPolling(this.data, responses)
        if (job) {
          try {
            await this.startAndWaitForJob(job)
            responses[step.getType()] = this.job
            this.job = null
          } catch (error) {
            this.creatingFailed = true
            return
          }
        }
        // Check if the step has a route, and overwrite that one. The user will be
        // redirected to the last route set.
        const completedRoute = step.getCompletedRoute(this.data, responses)
        if (completedRoute) {
          route = completedRoute
        }
      }

      await this.markAsComplete()

      // Clear all workspaces and application so that they're fetched again when
      // navigating to the dashboard. This will make sure that everything is correctly
      // loaded.
      await this.$store.dispatch('workspace/clearAll')
      await this.$store.dispatch('application/clearAll')

      this.$router.push(route)
    },
    /**
     * Mark the onboarding as completed, and redirect the user to the dashboard so
     * that they can start working with their database.
     */
    async markAsComplete() {
      try {
        const { data } = await AuthService(this.$client).update({
          completed_onboarding: true,
        })
        this.$store.dispatch('auth/forceUpdateUserData', { user: data })
      } catch (error) {
        notifyIf(error)
      }
    },
    /**
     * Called when the user clicks on the cancel button. This will stop the onboarding,
     * create an initial workspace, and mark it as completed.
     */
    async cancel() {
      this.cancelling = true
      try {
        const { data: workspace } = await WorkspaceService(
          this.$client
        ).createInitialWorkspace()

        for (const plugin of Object.values(this.$registry.getAll('plugin'))) {
          await plugin.initialWorkspaceCreated(workspace)
        }
      } catch (error) {
        notifyIf(error)
      }
      await this.markAsComplete()
      // Clear all workspaces and application so that they're fetched again when
      // navigating to the dashboard. This will make sure that everything is correctly
      // loaded.
      await this.$store.dispatch('workspace/clearAll')
      await this.$store.dispatch('application/clearAll')
      this.$router.push({ name: 'dashboard' })
    },
    updateData(data) {
      this.$set(this.data, this.step.getType(), data)
    },
    isValid() {
      const form = this.$refs?.form

      // It can be that the component hasn't been rendered yet. In that case, the button
      // must be disabled because we have to wait until it's rendered.
      if (!form) {
        return false
      }

      const isValid = form?.isValid
      if (typeof isValid === 'function') {
        return isValid()
      } else {
        throw new TypeError(
          'The onboarding form component must contain an `isValid` function.'
        )
      }
    },
    refresh() {
      this.reloading = true
      location.reload()
    },
    startAndWaitForJob(job) {
      this.startJobPoller(job)

      return new Promise((resolve, reject) => {
        const intervalId = setInterval(() => {
          if (this.jobHasSucceeded) {
            clearInterval(intervalId)
            resolve(job)
          } else if (this.jobHasFailed) {
            clearInterval(intervalId)
            reject(new Error('job failed'))
          }
        }, 100)
      })
    },
  },
}
</script>
