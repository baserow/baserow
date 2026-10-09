<template>
  <Modal ref="modal">
    <h2 class="box__title">{{ $t('agentBuilder.createAgent') }}</h2>
    <ApplicationForm
      :key="formKey"
      :default-values="{ name: defaultName }"
      :workspace="agentBuilder.workspace"
      :loading="loading"
      @submitted="createAgent"
    >
      <div class="actions actions--right">
        <Button size="large" :loading="loading" :disabled="loading">
          {{ $t('agentBuilder.createAgent') }}
        </Button>
      </div>
    </ApplicationForm>
  </Modal>
</template>

<script setup>
import { computed, ref } from 'vue'
import ApplicationForm from '@baserow/modules/core/components/application/ApplicationForm'
import { getNextAvailableNameInSequence } from '@baserow/modules/core/utils/string'
import { notifyIf } from '@baserow/modules/core/utils/error'

const props = defineProps({
  agentBuilder: { type: Object, required: true },
})
const { $store, $router, $i18n } = useNuxtApp()
const modal = ref(null)
const loading = ref(false)
const formKey = ref(0)
const defaultName = computed(() =>
  getNextAvailableNameInSequence(
    $i18n.t('agentBuilder.agent'),
    props.agentBuilder.agents.map(({ name }) => name)
  )
)

function show() {
  formKey.value++
  modal.value.show()
}

async function createAgent({ name }) {
  loading.value = true
  try {
    const agent = await $store.dispatch('agentBuilderAgent/create', {
      agentBuilder: props.agentBuilder,
      name,
    })
    modal.value.hide()
    await $router.push({
      name: 'agent-builder',
      params: { agentBuilderId: props.agentBuilder.id, agentId: agent.id },
    })
  } catch (error) {
    notifyIf(error, 'agentBuilderAgent')
  } finally {
    loading.value = false
  }
}

defineExpose({ show })
</script>
