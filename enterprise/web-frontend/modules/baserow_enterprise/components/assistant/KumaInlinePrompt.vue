<template>
  <div
    v-if="isAvailable"
    class="kuma-inline-prompt"
    :class="{ 'kuma-inline-prompt--open': isCardShown }"
  >
    <template v-if="!isCardShown">
      <span
        v-if="withDivider"
        class="kuma-inline-prompt__divider"
        aria-hidden="true"
      ></span>
      <button
        type="button"
        class="kuma-inline-prompt__link"
        @click="openPrompt()"
      >
        <i class="iconoir-sparks kuma-inline-prompt__sparks"></i>
        {{ linkLabel || $t('kumaInlinePrompt.createWithKuma') }}
      </button>
    </template>

    <div v-if="state === 'done'" role="status" class="kuma-inline-prompt__done">
      <span class="kuma-inline-prompt__done-summary">
        <i class="iconoir-sparks kuma-inline-prompt__sparks"></i>
        {{ summary }}
      </span>
      <span class="kuma-inline-prompt__done-actions">
        <ButtonText v-if="changed" type="primary" size="small" @click="undo()">
          {{ $t('kumaInlinePrompt.undo') }}
        </ButtonText>
        <ButtonIcon
          icon="iconoir-cancel"
          type="secondary"
          size="small"
          :aria-label="$t('kumaInlinePrompt.dismiss')"
          @click="dismiss()"
        ></ButtonIcon>
      </span>
    </div>

    <div v-if="isCardShown" class="kuma-inline-prompt__card">
      <div class="kuma-inline-prompt__header">
        <span class="kuma-inline-prompt__title">
          <i class="iconoir-sparks kuma-inline-prompt__sparks"></i>
          {{ title }}
        </span>
        <ButtonIcon
          v-if="state === 'open'"
          icon="iconoir-cancel"
          type="secondary"
          size="small"
          :aria-label="$t('kumaInlinePrompt.close')"
          @click="closePrompt()"
        ></ButtonIcon>
      </div>

      <template v-if="state === 'open'">
        <FormTextarea
          ref="textarea"
          v-model="prompt"
          class="kuma-inline-prompt__textarea"
          auto-expandable
          :min-rows="2"
          :max-rows="6"
          :aria-label="placeholder"
          :placeholder="placeholder"
          @keydown.enter.exact.prevent="submit()"
          @keydown.esc.prevent="closePrompt()"
        />
        <div v-if="suggestions.length" class="kuma-inline-prompt__suggestions">
          <button
            v-for="suggestion in suggestions"
            :key="suggestion.key"
            type="button"
            class="kuma-inline-prompt__suggestion"
            @click="useSuggestion(suggestion)"
          >
            {{ suggestion.label }}
          </button>
        </div>
        <div
          v-if="blockedMessage"
          class="kuma-inline-prompt__notice kuma-inline-prompt__notice--warning"
        >
          <i class="iconoir-warning-triangle"></i>
          {{ blockedMessage }}
        </div>
        <div
          v-if="errorMessage"
          class="kuma-inline-prompt__notice kuma-inline-prompt__notice--error"
        >
          <i class="iconoir-warning-circle"></i>
          {{ errorMessage }}
        </div>
      </template>

      <template v-else>
        <p class="kuma-inline-prompt__request">{{ prompt }}</p>
        <div role="status" class="kuma-inline-prompt__working">
          <span class="kuma-inline-prompt__dots" aria-hidden="true">
            <span></span><span></span><span></span>
          </span>
          {{ workingLabel }}
        </div>
      </template>

      <div class="kuma-inline-prompt__footer">
        <span class="kuma-inline-prompt__hint">
          {{ hint }}
        </span>
        <span class="kuma-inline-prompt__actions">
          <Button
            type="primary"
            size="small"
            icon="iconoir-sparks"
            :loading="state === 'working'"
            :disabled="!canSubmit"
            @click="submit()"
          >
            {{ submitButtonLabel }}
          </Button>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { useStore } from 'vuex'
import { isAssistantAvailable } from '@baserow_enterprise/utils/assistant'

/**
 * A small Kuma prompt shown in place, e.g. under a form: a link opens a card where
 * the user describes what they want, the host's `request` asks Kuma to do it, and
 * Kuma's summary is shown with an undo when something changed.
 *
 * The host provides what the request is about: the copy, the suggestions, a
 * message blocking the request when it can't be made yet, and `request`. It's only
 * shown when Kuma is available in the workspace, like the sidebar's Kuma AI item.
 */
const props = defineProps({
  /** Whether there is something to ask Kuma about, e.g. a saved data source. */
  enabled: { type: Boolean, default: true },
  /** The link opening the card. Defaults to "Create with Kuma AI". */
  linkLabel: { type: String, default: '' },
  title: { type: String, required: true },
  placeholder: { type: String, required: true },
  submitLabel: { type: String, required: true },
  /** Shown while Kuma works on the request. */
  workingLabel: { type: String, required: true },
  /** `{ key, label, prompt }` filling the textarea with `prompt` when clicked. */
  suggestions: { type: Array, default: () => [] },
  /** Why the request can't be sent yet. Disables the submit button. */
  blockedMessage: { type: String, default: '' },
  /**
   * Sends the user's request to Kuma. Resolves `{ changed, summary }`: whether
   * Kuma changed something, which can then be undone, and what it did.
   */
  request: { type: Function, required: true },
  /** The name of the error messages to show, see `getMessage`. */
  errorName: { type: String, default: null },
  /** Separates the link from the links before it in the same row. */
  withDivider: { type: Boolean, default: false },
})

/** `active` is emitted with whether the card is shown, e.g. to freeze a form. */
const emit = defineEmits(['active'])

const app = useNuxtApp()
const store = useStore()
const t = (key) => app.$i18n.t(key)

// idle → open → working → done, or back to open with an error.
const state = ref('idle')
const prompt = ref('')
const errorMessage = ref('')
const summary = ref('')
const changed = ref(false)
const textarea = ref(null)

const isAvailable = computed(() => {
  const workspace = store.getters['workspace/getSelected']
  return Boolean(
    props.enabled && workspace?.id && isAssistantAvailable(app, workspace)
  )
})

const isCardShown = computed(
  () => state.value === 'open' || state.value === 'working'
)

const canSubmit = computed(
  () =>
    state.value === 'open' &&
    prompt.value.trim() !== '' &&
    !props.blockedMessage
)

watch(isCardShown, (shown) => emit('active', shown))

// When Kuma stops being available, e.g. its model is switched off, close the card
// so the host isn't left waiting for it.
watch(isAvailable, (available) => {
  if (!available) {
    state.value = 'idle'
  }
})

const hint = computed(() => {
  if (state.value === 'working') {
    return t('kumaInlinePrompt.workingHint')
  }
  if (errorMessage.value) {
    return t('kumaInlinePrompt.tryAgainHint')
  }
  return t('kumaInlinePrompt.keyboardHint')
})

const submitButtonLabel = computed(() => {
  if (state.value === 'working') {
    return t('kumaInlinePrompt.working')
  }
  if (errorMessage.value) {
    return t('kumaInlinePrompt.tryAgain')
  }
  return props.submitLabel
})

async function focusTextarea() {
  await nextTick()
  textarea.value?.$el?.focus()
}

function openPrompt() {
  state.value = 'open'
  errorMessage.value = ''
  focusTextarea()
}

function closePrompt() {
  state.value = 'idle'
  errorMessage.value = ''
}

/** Hides Kuma's summary, e.g. once its undo would revert something else. */
function dismiss() {
  if (state.value === 'done') {
    state.value = 'idle'
  }
}

function useSuggestion(suggestion) {
  prompt.value = suggestion.prompt
  focusTextarea()
}

async function submit() {
  if (!canSubmit.value) {
    return
  }
  const message = prompt.value.trim()

  state.value = 'working'
  errorMessage.value = ''
  try {
    const result = await props.request(message)
    summary.value = result.summary
    changed.value = result.changed
    prompt.value = ''
    state.value = 'done'
  } catch (error) {
    state.value = 'open'
    if (!error.handler) {
      throw error
    }
    errorMessage.value = error.handler.getMessage(props.errorName).message
    error.handler.handled()
  }
}

async function undo() {
  state.value = 'idle'
  await store.dispatch('undoRedo/undo', { showLoadingToast: true })
}

defineExpose({ dismiss })
</script>
