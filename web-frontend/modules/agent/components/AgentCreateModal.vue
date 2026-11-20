<template>
  <Modal
    ref="modal"
    small
    :box-padding="false"
    :can-close="!loading"
    @show="reset"
  >
    <form class="agent-create" @submit.self.prevent="next">
      <div class="agent-create__head">
        <ButtonText
          v-if="step > STEP.DESCRIBE"
          type="secondary"
          button-type="button"
          icon="iconoir-nav-arrow-left"
          :aria-label="$t('action.back')"
          :disabled="loading"
          @click="step--"
        />
        <h2 class="agent-create__title">{{ $t(TITLES[step]) }}</h2>
      </div>
      <div class="agent-create__body">
        <Error :error="error" />
        <AgentCreateDescribeStep
          v-if="step === STEP.DESCRIBE"
          v-model="setup"
          :workspace="workspace"
        />
        <AgentCreateReviewStep
          v-else-if="step === STEP.REVIEW"
          v-model="setup"
          :workspace="workspace"
          :available-tools="availableTools"
          :can-bind-identity="canBindIdentity"
          :can-create-identity="canCreateIdentity"
          :new-identity-role="suggestedRole"
        />
        <AgentCreateModelStep
          v-else
          v-model="setup"
          :workspace="workspace"
          :available-tools="availableTools"
        />
      </div>
      <div class="agent-create__foot">
        <span v-if="step > STEP.DESCRIBE" class="agent-create__note">
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
          v-if="step < STEP.MODEL"
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
          :disabled="loading || !canCreate"
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
import AgentCreateModelStep from '@baserow/modules/agent/components/AgentCreateModelStep'
import AgentApplicationService from '@baserow/modules/agent/services/agentApplication'
import { FF_IDENTITIES } from '@baserow/modules/core/plugins/featureFlags'
import { getNextAvailableNameInSequence } from '@baserow/modules/core/utils/string'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { ResponseErrorMessage } from '@baserow/modules/core/plugins/clientHandler'
import {
  applyAgentSetup,
  createSetupIdentity,
  emptyAgentSetup,
  newIdentityRole,
} from '@baserow/modules/agent/utils/agentSetup'

const STEP = Object.freeze({ DESCRIBE: 1, REVIEW: 2, MODEL: 3 })
const TITLES = {
  [STEP.DESCRIBE]: 'agent.createApplication',
  [STEP.REVIEW]: 'agent.setupReviewTitle',
  [STEP.MODEL]: 'agent.setupModelTitle',
}

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
const step = ref(STEP.DESCRIBE)
const loading = ref(false)
const error = reactive({ visible: false, title: '', message: '' })
const canBindIdentity = computed(() =>
  $hasPermission('identity.bind', props.workspace, props.workspace.id)
)
const canCreateIdentity = computed(
  () =>
    canBindIdentity.value &&
    $featureFlagIsEnabled(FF_IDENTITIES) &&
    $hasPermission('identity.create', props.workspace, props.workspace.id)
)
const setup = ref(emptyAgentSetup('', props.workspace, false))
const availableTools = ref([])
const suggestedRole = computed(() =>
  newIdentityRole(props.workspace, setup.value, availableTools.value)
)
const hasName = computed(() => setup.value.name.trim().length > 0)
const canCreate = computed(
  () =>
    hasName.value &&
    (!setup.value.providerType || Boolean(setup.value.modelIdentifier))
)

function defaultName() {
  const excludeNames = store.getters['application/getAllOfWorkspace'](
    props.workspace
  ).map((application) => application.name)
  return getNextAvailableNameInSequence(
    props.applicationType.getDefaultName(),
    excludeNames
  )
}

async function loadAvailableTools() {
  try {
    const { data } = await AgentApplicationService($client).getWorkspaceTools(
      props.workspace.id
    )
    availableTools.value = data
  } catch (caught) {
    availableTools.value = []
    showError(caught)
  }
}

function reset() {
  step.value = STEP.DESCRIBE
  loading.value = false
  error.visible = false
  setup.value = emptyAgentSetup(
    defaultName(),
    props.workspace,
    canCreateIdentity.value
  )
  loadAvailableTools()
}

function next() {
  if (step.value < STEP.MODEL && hasName.value) step.value++
}

function showError(caught) {
  if (!caught.handler) throw caught
  const message = caught.handler.getMessage('application', null, {
    name: {
      invalid_name: new ResponseErrorMessage(
        t('identities.invalidNameTitle'),
        t('error.nameContainsUrl')
      ),
    },
  })
  error.title = message.title
  error.message = message.message
  error.visible = true
  caught.handler.handled()
}

async function create() {
  if (loading.value || !canCreate.value) return
  loading.value = true
  error.visible = false
  const context = { store, client: $client, registry: $registry, t }
  let created
  try {
    setup.value = await createSetupIdentity(
      context,
      props.workspace,
      setup.value,
      suggestedRole.value?.uid
    )
    created = await applyAgentSetup(context, props.workspace, setup.value)
  } catch (caught) {
    showError(caught)
    return
  } finally {
    loading.value = false
  }
  // The agent exists from here on, so nothing may offer to create it again.
  const { application, notApplied, webSearchWarning } = created
  emit('created', application)
  hide()
  if (webSearchWarning) {
    store.dispatch('toast/warning', {
      title: t('agent.setupPartialTitle'),
      message: webSearchWarning,
    })
  }
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
