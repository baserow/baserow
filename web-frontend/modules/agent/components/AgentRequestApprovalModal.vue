<template>
  <Modal
    ref="modal"
    small
    role="dialog"
    aria-modal="true"
    :aria-labelledby="titleId"
    :aria-describedby="descriptionId"
  >
    <template #content>
      <h2 :id="titleId" class="box__title">{{ $t('agent.askForApproval') }}</h2>
      <p :id="descriptionId">{{ $t('agent.askForApprovalWarning') }}</p>
      <PaginatedDropdown
        :key="pickerKey"
        :value="null"
        value-name="name"
        :fetch-page="fetchCandidates"
        :add-empty-item="false"
        :not-selected-text="$t('agent.chooseApprovers')"
        fixed-items
        fetch-on-open
        include-display-name-in-selected-event
        @input="choose"
      />
      <ul class="agent-approvers__list">
        <li
          v-for="person in chosen"
          :key="person.id"
          class="agent-approvers__item"
        >
          {{ person.name }}
          <ButtonIcon
            icon="iconoir-cancel"
            type="secondary"
            size="small"
            :aria-label="$t('agent.removeApprover', { name: person.name })"
            @click="remove(person.id)"
          />
        </li>
      </ul>
      <div class="actions actions--right actions--gap">
        <Button type="secondary" @click="modal.hide()">
          {{ $t('action.cancel') }}
        </Button>
        <Button :disabled="!chosen.length" @click="request">
          {{ $t('agent.askForApproval') }}
        </Button>
      </div>
    </template>
  </Modal>
</template>

<script setup>
import { ref, useId } from 'vue'
import { useNuxtApp } from '#app'
import PaginatedDropdown from '@baserow/modules/core/components/PaginatedDropdown'
import AgentApplicationService from '@baserow/modules/agent/services/agentApplication'

/** Picks the members asked to decide the held steps of a private conversation. */
const props = defineProps({
  agentId: { type: Number, required: true },
  conversationUuid: { type: String, default: null },
})
const emit = defineEmits(['request'])

const { $client } = useNuxtApp()
const service = AgentApplicationService($client)
const modal = ref(null)
const chosen = ref([])
// A new key empties the dropdown after each pick, so it reads as a picker.
const pickerKey = ref(0)
const titleId = useId()
const descriptionId = useId()

function show() {
  chosen.value = []
  pickerKey.value++
  modal.value.show()
}

function fetchCandidates(page, search) {
  return service.getApproverCandidates(
    props.agentId,
    props.conversationUuid,
    page,
    search
  )
}

function choose(selected) {
  const item = selected?.item
  if (item && !chosen.value.some((person) => person.id === item.id)) {
    chosen.value.push(item)
  }
  pickerKey.value++
}

function remove(id) {
  chosen.value = chosen.value.filter((person) => person.id !== id)
}

function request() {
  emit(
    'request',
    chosen.value.map((person) => person.id)
  )
  modal.value.hide()
}

defineExpose({ show })
</script>
