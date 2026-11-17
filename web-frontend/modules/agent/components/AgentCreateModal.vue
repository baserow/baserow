<template>
  <Modal
    ref="modal"
    small
    :box-padding="false"
    :can-close="!loading"
    @show="reset"
  >
    <form class="agent-create" @submit.prevent="next">
      <div class="agent-create__head">
        <ButtonText
          v-if="step === 2"
          type="secondary"
          button-type="button"
          icon="iconoir-nav-arrow-left"
          :aria-label="$t('action.back')"
          :disabled="loading"
          @click="step = 1"
        />
        <h2 class="agent-create__title">
          {{
            step === 1
              ? $t('agent.createApplication')
              : $t('agent.setupReviewTitle')
          }}
        </h2>
      </div>
      <div class="agent-create__body">
        <Error :error="error" />
        <AgentCreateDescribeStep v-if="step === 1" v-model="setup" />
        <AgentCreateReviewStep
          v-else
          v-model="setup"
          :workspace="workspace"
          :can-create-identity="canCreateIdentity"
        />
      </div>
      <div class="agent-create__foot">
        <span v-if="step === 2" class="agent-create__note">
          {{ $t('agent.setupLaterNote') }}
        </span>
        <Button
          type="secondary"
          button-type="button"
          :disabled="loading"
          @click="hide()"
        >
          {{ $t('action.cancel') }}
        </Button>
        <Button
          v-if="step === 1"
          type="primary"
          button-type="submit"
          :disabled="!hasName"
        >
          {{ $t('agent.setupContinue') }}
        </Button>
        <Button
          v-else
          type="primary"
          button-type="button"
          :loading="loading"
          :disabled="loading || !hasName"
          @click="create"
        >
          {{ $t('agent.createApplication') }}
        </Button>
      </div>
    </form>
  </Modal>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useStore } from 'vuex'
import Modal from '@baserow/modules/core/components/Modal'
import ButtonText from '@baserow/modules/core/components/ButtonText'
import AgentCreateDescribeStep from '@baserow/modules/agent/components/AgentCreateDescribeStep'
import AgentCreateReviewStep from '@baserow/modules/agent/components/AgentCreateReviewStep'
import { FF_IDENTITIES } from '@baserow/modules/core/plugins/featureFlags'
import { getNextAvailableNameInSequence } from '@baserow/modules/core/utils/string'
import { notifyIf } from '@baserow/modules/core/utils/error'
import {
  applyAgentSetup,
  emptyAgentSetup,
} from '@baserow/modules/agent/utils/agentSetup'

const props = defineProps({
  applicationType: { type: Object, required: true },
  workspace: { type: Object, required: true },
})
const emit = defineEmits(['created'])
const store = useStore()
const { t } = useI18n()
const { $client, $registry, $featureFlagIsEnabled, $hasPermission } =
  useNuxtApp()

const modal = ref(null)
const step = ref(1)
const loading = ref(false)
const error = reactive({ visible: false, title: '', message: '' })
const canCreateIdentity = computed(
  () =>
    $featureFlagIsEnabled(FF_IDENTITIES) &&
    $hasPermission('identity.create', props.workspace, props.workspace.id)
)
const setup = ref(emptyAgentSetup('', props.workspace, false))
const hasName = computed(() => setup.value.name.trim().length > 0)

function defaultName() {
  const excludeNames = store.getters['application/getAllOfWorkspace'](
    props.workspace
  ).map((application) => application.name)
  return getNextAvailableNameInSequence(
    props.applicationType.getDefaultName(),
    excludeNames
  )
}

function reset() {
  step.value = 1
  loading.value = false
  error.visible = false
  setup.value = emptyAgentSetup(
    defaultName(),
    props.workspace,
    canCreateIdentity.value
  )
}

function next() {
  if (step.value === 1 && hasName.value) step.value = 2
}

function showError(caught) {
  if (!caught.handler) throw caught
  const message = caught.handler.getMessage('application')
  error.title = message.title
  error.message = message.message
  error.visible = true
  caught.handler.handled()
}

async function create() {
  if (loading.value || !hasName.value) return
  loading.value = true
  error.visible = false
  let created
  try {
    created = await applyAgentSetup(
      { store, client: $client, registry: $registry, t },
      props.workspace,
      setup.value
    )
  } catch (caught) {
    showError(caught)
    return
  } finally {
    loading.value = false
  }
  // The agent exists from here on, so nothing may offer to create it again.
  const { application, notApplied } = created
  emit('created', application)
  hide()
  if (notApplied.length) {
    store.dispatch('toast/warning', {
      title: t('agent.setupPartialTitle'),
      message: t('agent.setupPartialMessage', {
        items: notApplied.join(', '),
      }),
    })
  }
  try {
    await store.dispatch('application/selectById', application.id)
    await props.applicationType.select(application)
  } catch (caught) {
    notifyIf(caught, 'application')
  }
}

const toggle = (...args) => modal.value?.toggle(...args)
const show = (...args) => modal.value?.show(...args)
const hide = (...args) => modal.value?.hide(...args)

defineExpose({ toggle, show, hide })
</script>
