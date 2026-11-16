<template>
  <div class="agent-action-inputs">
    <div class="agent-action-inputs__header">
      <h4>{{ $t('agent.actionInputs') }}</h4>
      <ButtonText
        v-if="editable && modelValue.length < 100"
        type="primary"
        size="small"
        button-type="button"
        icon="iconoir-plus"
        @click="addInput"
      >
        {{ $t('agent.addActionInput') }}
      </ButtonText>
    </div>
    <p class="agent-action-inputs__help">{{ $t('agent.actionInputsHelp') }}</p>
    <div
      v-for="input in modelValue"
      :key="input.id"
      class="agent-action-inputs__item"
      :class="{
        'agent-action-inputs__item--expanded': expandedIds.has(input.id),
      }"
    >
      <div class="agent-action-inputs__summary">
        <button
          type="button"
          class="agent-action-inputs__toggle"
          :aria-expanded="expandedIds.has(input.id)"
          @click="toggle(input.id)"
        >
          <i
            :class="
              expandedIds.has(input.id)
                ? 'iconoir-nav-arrow-down'
                : 'iconoir-nav-arrow-right'
            "
            aria-hidden="true"
          />
          <span class="agent-action-inputs__name">{{ input.name }}</span>
          <span class="agent-action-inputs__type">{{
            $t(inputTypeLabels[input.type])
          }}</span>
        </button>
        <Dropdown
          class="agent-action-inputs__requirement"
          :model-value="input.required"
          :disabled="!editable"
          :show-search="false"
          @update:model-value="update(input, { required: $event })"
        >
          <DropdownItem :value="true" :name="$t('agent.actionInputRequired')" />
          <DropdownItem
            :value="false"
            :name="$t('agent.actionInputOptional')"
          />
        </Dropdown>
      </div>
      <div
        v-show="expandedIds.has(input.id)"
        class="agent-action-inputs__editor"
      >
        <div class="agent-action-inputs__row">
          <FormGroup :label="$t('agent.actionInputName')" small-label required>
            <FormInput
              :model-value="input.name"
              :disabled="!editable"
              :maxlength="64"
              @update:model-value="update(input, { name: $event })"
            />
          </FormGroup>
          <FormGroup :label="$t('agent.actionInputType')" small-label required>
            <Dropdown
              :model-value="input.type"
              :disabled="!editable"
              @update:model-value="update(input, { type: $event })"
            >
              <DropdownItem
                v-for="(label, type) in inputTypeLabels"
                :key="type"
                :value="type"
                :name="$t(label)"
              />
            </Dropdown>
          </FormGroup>
        </div>
        <div class="agent-action-inputs__details">
          <FormGroup :label="$t('agent.actionInputDescription')" small-label>
            <FormInput
              :model-value="input.description"
              :maxlength="2000"
              :disabled="!editable"
              @update:model-value="update(input, { description: $event })"
            />
          </FormGroup>
        </div>
      </div>
      <footer
        v-if="editable"
        v-show="expandedIds.has(input.id)"
        class="agent-action-inputs__footer"
      >
        <ButtonText
          class="agent-action-inputs__delete"
          type="secondary"
          size="small"
          button-type="button"
          icon="iconoir-bin"
          :aria-label="$t('agent.removeActionInput', { name: input.name })"
          @click="remove(input)"
        >
          {{ $t('agent.deleteActionInput') }}
        </ButtonText>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { toRef } from 'vue'
import { useExpandedItems } from '@baserow/modules/agent/composables/useExpandedItems'
import { uuid } from '@baserow/modules/core/utils/string'
import ButtonText from '@baserow/modules/core/components/ButtonText'
import { ACTION_INPUT_TYPE_LABELS as inputTypeLabels } from '@baserow/modules/agent/utils/actionLabels'

const props = defineProps({
  modelValue: { type: Array, required: true },
  editable: Boolean,
})
const emit = defineEmits(['update:modelValue'])
const { expandedIds, toggle } = useExpandedItems(toRef(props, 'modelValue'))

function update(input, values) {
  if (!props.editable) return
  emit(
    'update:modelValue',
    props.modelValue.map((item) =>
      item.id === input.id ? { ...item, ...values } : item
    )
  )
}
function remove(input) {
  emit(
    'update:modelValue',
    props.modelValue.filter((item) => item.id !== input.id)
  )
}
function addInput() {
  const names = new Set(props.modelValue.map((input) => input.name))
  let name = 'input'
  for (let suffix = 2; names.has(name); suffix++) name = `input_${suffix}`
  const id = uuid()
  expandedIds.add(id)
  emit('update:modelValue', [
    ...props.modelValue,
    { id, name, type: 'string', description: '', required: true },
  ])
}
</script>
