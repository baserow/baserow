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
import { ref } from 'vue'
import MarkdownContext from '@baserow/modules/core/components/MarkdownContext'

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

const open = () => {
  if (context.value && toggle.value) {
    context.value.toggle(toggle.value, 'bottom', 'left', 4)
    emit('open')
  }
}
const hide = () => context.value?.hide()

defineExpose({ hide })
</script>
