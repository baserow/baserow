<template>
  <!-- Keyed by the phase, so that the toast of a failed install closes itself like
  the other error toasts, counted from when the failure shows. -->
  <Toast
    :key="phase"
    class="install-template-toast"
    :type="toastType"
    :icon="toastIcon"
    :loading="phase === 'running'"
    :close-button="phase === 'failed'"
    @close="autoClose"
  >
    <template #title>{{ title }}</template>
    <!-- Without a message, the toast mustn't render an empty paragraph. -->
    <template v-if="phase === 'running'" #default>{{ progress }} %</template>
    <template v-else-if="phase === 'failed'" #default>{{
      job.human_readable_error
    }}</template>
    <template v-if="phase === 'finished'" #actions>
      <button
        v-if="viewLabel"
        class="toast__actions-button toast__actions-button--primary install-template-toast__view"
        @click="view"
      >
        {{ viewLabel }}
      </button>
      <button
        class="toast__actions-button install-template-toast__dismiss"
        @click="dismiss"
      >
        {{ $t('InstallTemplateJobType.dismiss') }}
      </button>
    </template>
  </Toast>
</template>

<script setup>
import { computed, watch } from 'vue'
import { useStore } from 'vuex'
import { useNuxtApp } from '#app'

import Toast from '@baserow/modules/core/components/toasts/Toast'

const props = defineProps({
  // A toast of the `installTemplate` type. Its data holds the `jobId`, and the
  // final fields of the job once the job is removed from the job store.
  toast: {
    type: Object,
    required: true,
  },
})

const store = useStore()
const nuxtApp = useNuxtApp()
const { $i18n: i18n, $registry } = nuxtApp

// The job while it's in the job store, then the final fields written into the
// toast when the job ended.
const job = computed(
  () => store.getters['job/get'](props.toast.data.jobId) ?? props.toast.data
)

const phase = computed(() => {
  if (job.value.state === 'finished') {
    return 'finished'
  }
  if (job.value.state === 'failed') {
    return 'failed'
  }
  return 'running'
})

const templateName = computed(
  () => job.value.template?.name ?? props.toast.data.template_name ?? ''
)

const progress = computed(() => job.value.progress_percentage ?? 0)

const toastType = computed(
  () =>
    ({ finished: 'success', failed: 'error' })[phase.value] ?? 'info-primary'
)

const toastIcon = computed(
  () =>
    ({
      finished: 'iconoir-check-circle',
      failed: 'iconoir-warning-triangle',
    })[phase.value] ?? null
)

const title = computed(() => {
  const name = templateName.value
  if (phase.value === 'finished') {
    return i18n.t('InstallTemplateJobType.installedMessage', { name })
  }
  if (phase.value === 'failed') {
    return i18n.t('InstallTemplateJobType.failedTitle', { name })
  }
  return i18n.t('InstallTemplateJobType.installingTitle', { name })
})

// The first installed application, as it is in the application store if it was
// added there.
const firstApplication = computed(() => {
  const installed = job.value.installed_applications?.[0]
  if (!installed) {
    return null
  }
  return store.getters['application/get'](installed.id) ?? installed
})

const applicationType = computed(() => {
  const application = firstApplication.value
  if (!application || !$registry.exists('application', application.type)) {
    return null
  }
  return $registry.get('application', application.type)
})

const viewLabel = computed(() => applicationType.value?.getViewLabel() ?? null)

function remove() {
  store.dispatch('toast/remove', props.toast)
}

// A running install and the result with its link stay until dismissed.
function autoClose() {
  if (phase.value === 'failed') {
    remove()
  }
}

function dismiss() {
  remove()
}

// The job can leave the store without ending, when the target workspace is
// deleted or left for instance. Nothing would update the toast after that.
watch(
  () => store.getters['job/get'](props.toast.data.jobId),
  (current, previous) => {
    const ended = ['finished', 'failed'].includes(props.toast.data.state)
    if (previous && !current && !ended) {
      remove()
    }
  }
)

async function view() {
  const application = firstApplication.value
  remove()
  await applicationType.value.select(application, nuxtApp)
}
</script>
