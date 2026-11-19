<template>
  <Modal ref="modal" :can-close="!busy" small :aria-labelledby="titleId">
    <template #content>
      <h2 :id="titleId" class="box__title">{{ $t(titleKey) }}</h2>
      <p>{{ $t(descriptionKey) }}</p>
      <template v-if="mode === 'request'">
        <PaginatedDropdown
          :key="selectionVersion"
          :value="null"
          value-name="name"
          :fetch-page="fetchPeople"
          :add-empty-item="false"
          :not-selected-text="$t('agent.chooseApprovers')"
          fixed-items
          fetch-on-open
          include-display-name-in-selected-event
          @input="selectPerson"
        />
        <ul class="agent-audience__people">
          <li v-for="person in people" :key="person.id">
            {{ person.name }}
            <ButtonIcon
              icon="iconoir-cancel"
              type="secondary"
              size="small"
              :aria-label="$t('agent.removePerson', { name: person.name })"
              @click="removePerson(person.id)"
            />
          </li>
        </ul>
      </template>
      <div class="actions actions--right actions--gap margin-top-2">
        <Button type="secondary" :disabled="busy" @click="modal.hide()">{{
          $t('action.cancel')
        }}</Button>
        <Button
          v-if="mode === 'delete'"
          type="secondary"
          :disabled="busy"
          @click="submit('me')"
          >{{ $t('agent.deleteForMe') }}</Button
        >
        <Button
          :type="mode === 'delete' ? 'danger' : 'primary'"
          :disabled="busy || (mode === 'request' && !people.length)"
          :loading="busy"
          @click="submit('everyone')"
          >{{ $t(confirmKey) }}</Button
        >
      </div>
    </template>
  </Modal>
</template>

<script setup>
import { computed, ref, useId } from 'vue'
import PaginatedDropdown from '@baserow/modules/core/components/PaginatedDropdown'
import AgentApplicationService from '@baserow/modules/agent/services/agentApplication'
import { notifyIf } from '@baserow/modules/core/utils/error'
const props = defineProps({ agentId: { type: Number, required: true } })
const emit = defineEmits(['changed', 'deleted'])
const { $client } = useNuxtApp()
const service = AgentApplicationService($client)
const modal = ref(null)
const mode = ref('share')
const target = ref(null)
const reply = ref(null)
const busy = ref(false)
const people = ref([])
const selectionVersion = ref(0)
const titleId = useId()
const labels = {
  share: [
    'agent.shareConversation',
    'agent.shareWarning',
    'agent.shareConversation',
  ],
  delete: [
    'agent.deleteConversation',
    'agent.deleteAudienceWarning',
    'agent.deleteForEveryone',
  ],
  request: [
    'agent.askForApproval',
    'agent.approverAudienceWarning',
    'agent.askForApproval',
  ],
}
const titleKey = computed(() => labels[mode.value][0])
const descriptionKey = computed(() => labels[mode.value][1])
const confirmKey = computed(() => labels[mode.value][2])
function show(action, conversation, replyUuid = null) {
  if (busy.value) return
  mode.value = action
  target.value = conversation
  reply.value = replyUuid
  people.value = []
  selectionVersion.value++
  modal.value.show()
}
async function fetchPeople(page, search) {
  return service.getApprovalRecipients(
    props.agentId,
    target.value.uuid,
    page,
    search
  )
}
function selectPerson(value) {
  if (
    value?.item &&
    !people.value.some((person) => person.id === value.item.id)
  )
    people.value.push(value.item)
  selectionVersion.value++
}
function removePerson(id) {
  people.value = people.value.filter((person) => person.id !== id)
  selectionVersion.value++
}
async function submit(scope) {
  if (busy.value) return
  busy.value = true
  const conversation = target.value
  try {
    if (mode.value === 'delete') {
      if (scope === 'me') {
        const { data } = await service.leaveConversation(
          props.agentId,
          conversation.uuid
        )
        emit('deleted', conversation, data.trashed)
      } else {
        await service.deleteConversation(props.agentId, conversation.uuid)
        emit('deleted', conversation, true)
      }
    } else {
      const response =
        mode.value === 'share'
          ? await service.shareConversation(props.agentId, conversation.uuid)
          : await service.requestApproval(
              props.agentId,
              conversation.uuid,
              reply.value,
              people.value.map((person) => person.id)
            )
      emit('changed', response.data)
    }
    modal.value.hide()
  } catch (error) {
    notifyIf(error)
  } finally {
    busy.value = false
  }
}
defineExpose({ show })
</script>
