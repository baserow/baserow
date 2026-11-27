<template>
  <FormGroup
    horizontal-narrow
    small-label
    required
    class="margin-bottom-2"
    :label="label"
    :helper-text="helperText"
  >
    <div
      class="agent-channel-color-field flex align-items-center"
      :inert="!canEdit || null"
    >
      <ColorInput
        :model-value="draft || AUTOMATIC"
        :color-variables="automaticVariables"
        :allow-opacity="false"
        small
        @update:model-value="pick"
      />
      <ButtonText
        v-if="canEdit && draft"
        size="small"
        button-type="button"
        @click="reset"
      >
        {{ $t('agentChannels.resetColor') }}
      </ButtonText>
    </div>
  </FormGroup>
</template>

<script setup>
import { computed, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import debounce from 'lodash/debounce'
import ButtonText from '@baserow/modules/core/components/ButtonText'
import ColorInput from '@baserow/modules/core/components/ColorInput'
import { useChannelDraft } from '@baserow_enterprise/composables/useAgentChannels'

const AUTOMATIC = 'automatic'
const SAVE_DELAY_MS = 400

const props = defineProps({
  /** The channel as its card shows it, edits included. */
  channel: { type: Object, required: true },
  /** The `#rrggbb` field the row edits; blank is the page's own colour. */
  field: { type: String, required: true },
  label: { type: String, required: true },
  /** What the page shows for a blank colour, as the Automatic swatch. */
  automaticColor: { type: String, required: true },
  helperText: { type: String, default: null },
  /** Whether the user may change the channel. */
  canEdit: Boolean,
})
const emit = defineEmits(['update'])
const { t } = useI18n()
const { draftOf, save } = useChannelDraft(props, emit)

const draft = draftOf(props.field)
const automaticVariables = computed(() => [
  {
    value: AUTOMATIC,
    color: props.automaticColor,
    name: t('agentChannels.automatic'),
  },
])
const debouncedSave = debounce(
  (value) => save(props.field, value),
  SAVE_DELAY_MS
)

/** The picker reports every step of a drag; only where it stops is saved. */
function pick(value) {
  if (value === AUTOMATIC) return reset()
  draft.value = value.toLowerCase()
  debouncedSave(draft.value)
}

function reset() {
  debouncedSave.cancel()
  draft.value = ''
  save(props.field, '')
}

onBeforeUnmount(() => debouncedSave.flush())
</script>
