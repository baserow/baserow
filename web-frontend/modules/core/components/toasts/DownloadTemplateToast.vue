<template>
  <!-- Keyed by the phase, so that the toast of a failed download closes itself
  like the other error toasts, counted from when the failure shows. -->
  <Toast
    :key="phase"
    class="download-template-toast"
    :type="toastType"
    :icon="toastIcon"
    :loading="phase === 'running'"
    :close-button="phase === 'failed'"
    @close="autoClose"
  >
    <template #title>{{ title }}</template>
    {{ message }}
    <template v-if="phase === 'finished'" #actions>
      <button
        v-if="toast.data.url"
        class="toast__actions-button toast__actions-button--primary download-template-toast__download"
        :class="{ 'toast__actions-button--loading': toast.data.downloading }"
        :disabled="toast.data.downloading"
        @click="downloadArchive"
      >
        {{ $t('downloadTemplateToast.download') }}
      </button>
      <button
        class="toast__actions-button download-template-toast__dismiss"
        @click="remove"
      >
        {{ $t('downloadTemplateToast.dismiss') }}
      </button>
    </template>
  </Toast>
</template>

<script setup>
import { computed } from 'vue'
import { useStore } from 'vuex'
import { useNuxtApp } from '#app'

import Toast from '@baserow/modules/core/components/toasts/Toast'

const props = defineProps({
  // A toast of the `downloadTemplate` type. Its data holds the `jobId` of the
  // build, the name of the template when the download was clicked in this page,
  // the error of a failed build, the `url` and `file_name` of the archive, and
  // whether it's being saved.
  toast: {
    type: Object,
    required: true,
  },
})

const store = useStore()
const { $i18n: i18n, $registry } = useNuxtApp()

// The job while it's in the job store, then the fields written into the toast
// when the job ended.
const job = computed(
  () => store.getters['job/get'](props.toast.data.jobId) ?? props.toast.data
)

// A finished build is still running until the archive is handed out.
const phase = computed(() => {
  if (props.toast.data.url) {
    return 'finished'
  }
  if (job.value.state === 'failed') {
    return 'failed'
  }
  return 'running'
})

// A download started before the page was loaded has only the name of the file.
const name = computed(
  () => props.toast.data.template_name ?? props.toast.data.file_name ?? ''
)

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
  if (phase.value === 'finished') {
    return i18n.t('downloadTemplateToast.readyTitle')
  }
  if (phase.value === 'failed') {
    return i18n.t('downloadTemplateToast.failedTitle')
  }
  return i18n.t('downloadTemplateToast.preparingTitle')
})

const message = computed(() => {
  const params = { name: name.value }
  if (phase.value === 'finished') {
    return i18n.t('downloadTemplateToast.readyMessage', params)
  }
  if (phase.value === 'failed') {
    return job.value.human_readable_error
  }
  return i18n.t('downloadTemplateToast.preparingMessage', params)
})

function remove() {
  store.dispatch('toast/remove', props.toast)
}

// A running download and the ready archive stay until dismissed.
function autoClose() {
  if (phase.value === 'failed') {
    remove()
  }
}

async function downloadArchive() {
  await $registry
    .get('job', 'download_user_template')
    .downloadArchive(props.toast.data, props.toast)
}
</script>
