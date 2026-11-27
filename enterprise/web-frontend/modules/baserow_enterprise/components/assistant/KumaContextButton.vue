<template>
  <button
    v-if="available"
    ref="trigger"
    v-tooltip="tooltip"
    type="button"
    class="kuma-context-button"
    :aria-label="tooltip"
    :aria-pressed="selected"
    @click.stop="attach"
  >
    <i class="iconoir-sparks" aria-hidden="true"></i>
  </button>
</template>

<script setup>
import {
  computed,
  inject,
  onBeforeUnmount,
  onMounted,
  ref,
  useId,
  watch,
  watchEffect,
} from 'vue'
import { useStore } from 'vuex'
import { uuid } from '@baserow/modules/core/utils/string'
import { isAssistantAvailable } from '@baserow_enterprise/utils/assistant'

const props = defineProps({
  enabled: { type: Boolean, default: true },
  workspace: { type: Object, default: null },
  label: { type: String, default: '' },
  title: { type: String, required: true },
  placeholder: { type: String, required: true },
  blockedMessage: { type: String, default: '' },
  action: { type: String, required: true },
  parameters: { type: Object, required: true },
})
const emit = defineEmits(['active', 'completed'])
const app = useNuxtApp()
const editor = app.$kumaEditor
const store = useStore()
const workspace = computed(
  () => props.workspace || store.getters['workspace/getSelected']
)
const available = computed(
  () =>
    props.enabled &&
    workspace.value?.id &&
    isAssistantAvailable(app, workspace.value)
)
const tooltip = computed(() => app.$i18n.t(`kumaPrompt.${props.action}Tooltip`))
const id = useId()
const trigger = ref(null)
const selected = computed(() => editor.target.value?.id === id)
const isOverlayOpen = inject('isOverlayOpen', () => true)
const register = inject('registerChild', null)
const unregister = inject('unregisterChild', null)
// The sidebar belongs to this editor for outside-click handling, including nested menus.
const child = {
  getTeleportedElement: () => (selected.value ? editor.panel.value : null),
}

// Teleported editors are positioned against the viewport, outside the resizable layout.
watchEffect(
  (onCleanup) => {
    const panel = editor.panel.value
    const origin = trigger.value?.closest('.context, .modal__wrapper')
    if (!selected.value || !panel || !origin) return
    let availableWidth
    const position = () => {
      const edge = panel.getBoundingClientRect().left
      if (origin.matches('.modal__wrapper')) {
        origin.style.setProperty(
          '--kuma-sidebar-width',
          window.innerWidth - edge + 'px'
        )
      } else {
        const width = Math.max(0, edge - 16)
        if (width !== availableWidth) {
          origin.removeAttribute('data-kuma-constrained')
          availableWidth = width
        }
        if (origin.offsetWidth > width) {
          origin.style.setProperty('--kuma-editor-width', width + 'px')
          origin.setAttribute('data-kuma-constrained', '')
        }
        const left = origin.offsetLeft
        const shift = Math.min(0, edge - 8 - left - origin.offsetWidth)
        origin.style.setProperty(
          '--kuma-editor-offset',
          Math.max(8 - left, shift) + 'px'
        )
      }
    }
    const observer = new ResizeObserver(position)
    observer.observe(panel)
    observer.observe(origin)
    window.addEventListener('resize', position)
    position()
    onCleanup(() => {
      observer.disconnect()
      window.removeEventListener('resize', position)
      origin.style.removeProperty('--kuma-sidebar-width')
      origin.style.removeProperty('--kuma-editor-offset')
      origin.style.removeProperty('--kuma-editor-width')
      origin.removeAttribute('data-kuma-constrained')
    })
  },
  { flush: 'post' }
)

function detach() {
  if (selected.value) editor.target.value = null
}
function attach() {
  if (selected.value) {
    editor.panel.value?.querySelector('textarea')?.focus()
    return
  }
  const chat = store.getters['assistant/currentChat']
  const saved = chat?.editorContext
  const target = saved?.target
  const resume =
    saved?.action === props.action &&
    saved.location.workspace.id === workspace.value.id &&
    (target.view_id || target.field_id || target.agent_id || target.id) &&
    Object.entries(target).every(
      ([key, value]) => props.parameters[key] === value
    )
  editor.target.value = {
    id,
    chatUuid: resume ? chat.id : uuid(),
    previousTurns: resume
      ? store.getters['assistant/messages'].map((message) => ({
          text: message.content,
          own: message.role === 'human',
        }))
      : [],
    workspaceId: workspace.value.id,
    action: props.action,
    starter: app.$i18n.t(`kumaPrompt.${props.action}Starter`),
    get title() {
      return props.title
    },
    get label() {
      return props.label
    },
    get placeholder() {
      return props.placeholder
    },
    get blockedMessage() {
      return props.blockedMessage
    },
    get parameters() {
      return props.parameters
    },
    busy(value) {
      emit('active', value)
    },
    apply(result) {
      emit('completed', result)
    },
    focus() {
      trigger.value?.focus()
    },
    undoable: ref(false),
  }
  app.$bus.$emit('toggle-right-sidebar', true)
}

function dismiss() {
  if (selected.value) editor.target.value.undoable.value = false
}
watch(
  () => available.value && isOverlayOpen(),
  (shown) => {
    if (!shown) detach()
  },
  { flush: 'sync' }
)
watch(() => workspace.value?.id, detach)
onMounted(() => register?.(child))
onBeforeUnmount(() => {
  detach()
  unregister?.(child)
})
defineExpose({ dismiss })
</script>
