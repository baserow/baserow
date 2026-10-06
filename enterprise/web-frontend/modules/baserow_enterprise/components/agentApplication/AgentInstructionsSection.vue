<template>
  <div>
    <FormTextarea
      v-model="value"
      :rows="14"
      :disabled="!canUpdate"
      :placeholder="$t('agentInstructions.placeholder')"
      @input="onInput"
    ></FormTextarea>
    <PromptAttachments
      v-if="workspace"
      :workspace="workspace"
      :attachments="skillAttachments"
      :disabled="!canUpdate"
      @add="saveSkills([...skillAttachments, $event])"
      @update="
        saveSkills(
          skillAttachments.map((item) =>
            item.id === $event.id ? $event : item
          )
        )
      "
      @remove="
        saveSkills(skillAttachments.filter((item) => item.id !== $event.id))
      "
    />
    <div class="agent-configuration__hint">
      {{ $t('agentInstructions.hint') }}
    </div>
    <div class="agent-configuration__actions">
      <Button
        v-if="canUpdate"
        type="secondary"
        icon="iconoir-sparks"
        :loading="improving"
        @click="improve"
      >
        {{ $t('agentInstructions.improve') }}
      </Button>
      <span class="agent-configuration__counter">
        {{ $t('agentInstructions.characters', { count: value.length }) }}
      </span>
    </div>
  </div>
</template>

<script>
import { defineComponent, ref, toRef, computed } from 'vue'
import { useStore } from 'vuex'
import PromptAttachments from '@baserow/modules/core/components/promptAttachments/PromptAttachments'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { useSeededAgentField } from '@baserow_enterprise/composables/useSeededAgentField'
import { useAgentContext } from '@baserow_enterprise/composables/useAgentContext'

export default defineComponent({
  name: 'AgentInstructionsSection',
  components: { PromptAttachments },
  props: {
    application: {
      type: Object,
      required: true,
    },
    canUpdate: {
      type: Boolean,
      required: true,
    },
  },
  setup(props) {
    const store = useStore()
    const { storePrefix } = useAgentContext()
    const { agent, value, onInput, setValue, flush } = useSeededAgentField(
      'instructions',
      { canUpdate: toRef(props, 'canUpdate') }
    )

    const improving = ref(false)
    const improve = async () => {
      if (improving.value || !agent.value) {
        return
      }
      improving.value = true
      try {
        // Persist what the user typed before asking for the improved version.
        flush()
        const instructions = await store.dispatch(
          `${storePrefix}agentApplication/improveInstructions`,
          { agentId: agent.value.id, instructions: value.value }
        )
        setValue(instructions)
      } catch (error) {
        notifyIf(error, 'application')
      } finally {
        improving.value = false
      }
    }

    // The workspace skills the agent follows are attachments of its
    // instructions: `{ type: 'skill', id, mode }` in the generic picker, saved
    // as the agent's skill links.
    const workspace = computed(() =>
      store.getters['workspace/get'](props.application.workspace.id)
    )
    const skillAttachments = computed(() =>
      (agent.value?.skills || []).map((entry) => ({
        type: 'skill',
        id: entry.skill_id,
        mode: entry.mode,
      }))
    )
    const saveSkills = async (attachments) => {
      try {
        await store.dispatch(`${storePrefix}agentApplication/update`, {
          agentId: agent.value.id,
          values: {
            skills: attachments.map(({ id, mode }) => ({
              skill_id: id,
              mode,
            })),
          },
        })
      } catch (error) {
        notifyIf(error, 'application')
      }
    }

    return {
      value,
      onInput,
      improving,
      improve,
      workspace,
      skillAttachments,
      saveSkills,
    }
  },
})
</script>
