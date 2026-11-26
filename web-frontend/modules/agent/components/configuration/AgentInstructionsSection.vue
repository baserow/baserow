<template>
  <FormGroup
    :label="$t('agent.instructions')"
    :error="Boolean(errors.instructions)"
    :error-message="
      sectionType.getFieldErrorMessage('instructions', errors.instructions)
    "
    :helper-text="$t('agent.instructionsHelper')"
    small-label
    required
  >
    <FormTextarea
      ref="instructionsInput"
      :model-value="configuration.instructions || ''"
      :error="Boolean(errors.instructions)"
      :disabled="!editable"
      :rows="10"
      :maxlength="100000"
      @update:model-value="$emit('change', { instructions: $event })"
      @blur="$emit('flush')"
    />
  </FormGroup>
  <section class="agent-suggested-messages">
    <div class="agent-suggested-messages__header">
      <h3 class="agent-suggested-messages__title">
        {{ $t('agent.suggestedMessages') }}
      </h3>
      <ButtonText
        v-if="editable && rows.length < AGENT_SUGGESTED_MESSAGES_MAX"
        type="primary"
        size="small"
        button-type="button"
        icon="iconoir-plus"
        class="agent-suggested-messages__add"
        @click="addRow"
      >
        {{ $t('agent.addSuggestedMessage') }}
      </ButtonText>
    </div>
    <p class="agent-suggested-messages__description">
      {{ $t('agent.suggestedMessagesDescription') }}
    </p>
    <p v-if="!rows.length" class="agent-suggested-messages__empty">
      {{ $t('agent.noSuggestedMessages') }}
    </p>
    <ul v-else class="agent-suggested-messages__list">
      <li
        v-for="(row, index) in rows"
        :key="row.id"
        class="agent-suggested-messages__item"
      >
        <FormGroup
          class="agent-suggested-messages__input"
          :label="$t('agent.suggestedMessageLabel', { number: index + 1 })"
          required
        >
          <FormInput
            :ref="(input) => (rowInputs[row.id] = input)"
            :model-value="row.text"
            :disabled="!editable"
            :maxlength="AGENT_SUGGESTED_MESSAGE_MAX_LENGTH"
            @update:model-value="editRow(row, $event)"
            @blur="blurRow(row)"
          />
        </FormGroup>
        <ButtonIcon
          v-if="editable"
          icon="iconoir-bin"
          :aria-label="$t('agent.removeSuggestedMessage')"
          :title="$t('agent.removeSuggestedMessage')"
          @click="removeRow(row)"
        />
      </li>
    </ul>
  </section>
</template>

<script setup>
import { nextTick, ref, watch } from 'vue'
import isEqual from 'lodash/isEqual'
import { uuid } from '@baserow/modules/core/utils/string'
import {
  AGENT_SUGGESTED_MESSAGE_MAX_LENGTH,
  AGENT_SUGGESTED_MESSAGES_MAX,
} from '@baserow/modules/agent/constants'

defineOptions({ inheritAttrs: false })
const props = defineProps({
  configuration: { type: Object, required: true },
  errors: { type: Object, required: true },
  sectionType: { type: Object, required: true },
  editable: Boolean,
})
const emit = defineEmits(['change', 'flush'])
const instructionsInput = ref(null)
const rowInputs = {}

const toRows = (messages) =>
  (messages || []).map((text) => ({ id: uuid(), text }))
const savedMessages = () =>
  rows.value.map((row) => row.text.trim()).filter(Boolean)
const rows = ref(toRows(props.configuration.suggested_messages))

watch(
  () => props.configuration.suggested_messages,
  (messages = []) => {
    if (!isEqual(messages, savedMessages())) rows.value = toRows(messages)
  }
)

function emitChange() {
  emit('change', { suggested_messages: savedMessages() })
}

function editRow(row, text) {
  row.text = text
  emitChange()
}

function withoutRow(row) {
  rows.value = rows.value.filter((other) => other.id !== row.id)
}

function blurRow(row) {
  if (!row.text.trim()) withoutRow(row)
  emit('flush')
}

function removeRow(row) {
  withoutRow(row)
  emitChange()
  emit('flush')
}

async function addRow() {
  const row = { id: uuid(), text: '' }
  rows.value.push(row)
  await nextTick()
  rowInputs[row.id]?.focus()
}

function focusField() {
  instructionsInput.value?.focus()
}

defineExpose({ focusField })
</script>
