<template>
  <button
    v-if="note"
    ref="toggle"
    v-bind="$attrs"
    type="button"
    class="note-indicator"
    draggable="false"
    :title="$t('noteIndicator.show')"
    :aria-label="$t('noteIndicator.show')"
    @mousedown.prevent
    @click.stop="open()"
  >
    <i class="iconoir-notes"></i>
  </button>
  <MarkdownContext
    v-if="note"
    ref="context"
    :title="$t('noteIndicator.title')"
    :content="note"
  />
</template>

<script setup>
import { onBeforeUnmount, ref } from 'vue'
import MarkdownContext from '@baserow/modules/core/components/MarkdownContext'
import { openNote } from '@baserow/modules/core/utils/openNote'

/**
 * An icon shown on an object that has a note (see the backend `NoteMixin`).
 * Clicking it opens the note, rendered from Markdown. Renders nothing when the
 * note is empty.
 */
defineOptions({ inheritAttrs: false })

defineProps({
  note: {
    type: String,
    required: false,
    default: '',
  },
})

const emit = defineEmits(['open'])

const toggle = ref(null)
const context = ref(null)

const hide = () => context.value?.hide()

const open = () => {
  if (context.value && toggle.value) {
    // The click on the icon does not reach the page, so the note that is
    // already open would not see it as a click outside and would stay open.
    if (openNote.hide && openNote.hide !== hide) {
      openNote.hide()
    }
    openNote.hide = hide
    context.value.toggle(toggle.value, 'bottom', 'left', 4)
    emit('open')
  }
}

onBeforeUnmount(() => {
  if (openNote.hide === hide) {
    openNote.hide = null
  }
})

defineExpose({ hide })
</script>
