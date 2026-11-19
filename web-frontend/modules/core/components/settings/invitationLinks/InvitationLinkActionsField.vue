<template>
  <div class="invitation-link-actions-field">
    <button
      v-tooltip="$t('inviteModal.linkCopy')"
      type="button"
      class="invitation-link-actions-field__action"
      :aria-label="$t('inviteModal.linkCopy')"
      @click="copy"
    >
      <i class="iconoir-copy" aria-hidden="true"></i>
      <Copied ref="copied"></Copied>
    </button>
    <button
      v-tooltip="$t('inviteModal.linkDelete')"
      type="button"
      class="invitation-link-actions-field__action"
      :aria-label="$t('inviteModal.linkDelete')"
      @click="$emit('delete-link', row)"
    >
      <i class="iconoir-bin" aria-hidden="true"></i>
    </button>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useNuxtApp, useRuntimeConfig } from '#imports'
import { copyToClipboard } from '@baserow/modules/core/utils/clipboard'

const props = defineProps({
  row: { type: Object, required: true },
  column: { type: Object, required: true },
})
defineEmits(['delete-link'])

const { $router } = useNuxtApp()
const config = useRuntimeConfig()
const copied = ref(null)

function copy() {
  const path = $router.resolve({
    name: 'invitation-link',
    params: { slug: props.row.slug },
  }).href
  copyToClipboard(config.public.publicWebFrontendUrl + path)
  copied.value?.show()
}
</script>
