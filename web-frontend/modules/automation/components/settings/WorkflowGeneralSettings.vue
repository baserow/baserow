<template>
  <div ref="root">
    <h2 class="box__title">
      {{ $t('workflowGeneralSettings.titleOverview') }}
    </h2>

    <FormGroup
      small-label
      :label="$t('workflowGeneralSettings.nameLabel')"
      :error-message="getFirstErrorMessage('name')"
      required
    >
      <FormInput v-model="v$.values.name.$model" size="large"></FormInput>
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('workflowGeneralSettings.workflowDisabledRecipientsLabel')"
      class="padding-top-2"
      :helper-text="
        $t('workflowGeneralSettings.workflowDisabledRecipientsHelp')
      "
      required
    >
      <div v-if="selectedWorkflowRecipients.length > 0">
        <Badge
          v-for="recipient in selectedWorkflowRecipients"
          :key="recipient.id"
          class="margin-right-1 margin-top-1"
          rounded
          :title="recipient.email"
        >
          {{ recipient.name }}
        </Badge>
      </div>
      <div v-else class="margin-top-2">
        {{ $t('workflowGeneralSettings.noWorkflowDisabledRecipients') }}
      </div>
      <div class="margin-top-1">
        <Button type="secondary" @click="openRecipientModal">
          {{ $t('workflowGeneralSettings.selectWorkflowDisabledRecipients') }}
        </Button>
      </div>
    </FormGroup>

    <MemberAssignmentModal
      ref="workflowDisabledRecipientsModal"
      :members="workspaceMembers"
      :selected-members="selectedWorkspaceMembers"
      :allow-empty-selection="true"
      :button-label="$t('action.select')"
      @select="updateWorkflowDisabledRecipients"
    />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, toRef } from 'vue'
import { useStore } from 'vuex'
import { useNuxtApp } from '#imports'
import { useI18n } from 'vue-i18n'
import { useVuelidate } from '@vuelidate/core'
import { maxLength, required, helpers } from '@vuelidate/validators'
import debounce from 'lodash/debounce'
import { useForm } from '@baserow/modules/core/composables/useForm'
import WorkspaceService from '@baserow/modules/core/services/workspace'
import { notifyIf } from '@baserow/modules/core/utils/error'
import MemberAssignmentModal from '@baserow/modules/core/components/workspace/MemberAssignmentModal'
import { clone } from '@baserow/modules/core/utils/object'

defineOptions({
  name: 'WorkflowGeneralSettings',
})

const props = defineProps({
  automation: {
    type: Object,
    required: true,
  },
  workflow: {
    type: Object,
    required: true,
  },
  defaultValues: {
    type: Object,
    required: false,
    default: () => {
      return {}
    },
  },
  disabled: {
    type: Boolean,
    required: false,
    default: false,
  },
})

const emit = defineEmits(['submitted', 'values-changed'])

const { $client } = useNuxtApp()
const { t } = useI18n()
const store = useStore()
const root = ref(null)
const workflowDisabledRecipientsModal = ref(null)
const workspaceMembers = ref([])
const membersLoading = ref(false)
const values = reactive({
  name: '',
  notification_recipient_ids: [],
})
const allowedValues = ['name', 'notification_recipient_ids']

const rules = computed(() => ({
  values: {
    name: {
      required: helpers.withMessage(t('error.requiredField'), required),
      maxLength: helpers.withMessage(
        t('error.maxLength', { max: 255 }),
        maxLength(255)
      ),
    },
  },
}))
const v$ = useVuelidate(rules, { values }, { $lazy: true })

const loadWorkspaceMembers = async () => {
  if (membersLoading.value || workspaceMembers.value.length) {
    return
  }

  try {
    membersLoading.value = true
    const { data } = await WorkspaceService($client).fetchAllUsers(
      props.automation.workspace.id
    )
    workspaceMembers.value = data
  } catch (error) {
    notifyIf(error, 'workspace')
  } finally {
    membersLoading.value = false
  }
}

const openRecipientModal = async () => {
  await loadWorkspaceMembers()
  workflowDisabledRecipientsModal.value?.show()
}

onMounted(() => {
  loadWorkspaceMembers()
})

const selectedWorkflowRecipientIds = computed(
  () => values.notification_recipient_ids || []
)
const selectedWorkspaceMembers = computed(() =>
  workspaceMembers.value.filter((member) =>
    selectedWorkflowRecipientIds.value.includes(member.user_id)
  )
)
const selectedWorkflowRecipients = computed(() =>
  selectedWorkspaceMembers.value.map(({ user_id, name, email }) => ({
    id: user_id,
    name,
    email,
  }))
)

const debouncedUpdateWorkflow = debounce((updatedValues) => {
  updateWorkflow(updatedValues)
}, 300)

const form = useForm({
  defaultValues: toRef(props, 'defaultValues'),
  values,
  allowedValues,
  emit,
  v$,
  root,
  emitChange(newValues) {
    debouncedUpdateWorkflow(newValues)
  },
})

const updateWorkflow = async (updatedValues) => {
  if (!form.isFormValid()) {
    return
  }

  try {
    await store.dispatch('automationWorkflow/update', {
      automation: props.automation,
      workflow: props.workflow,
      values: clone(updatedValues),
    })
  } catch (error) {
    notifyIf(error, 'automationWorkflow')
    await form.reset()
  }
}

const getFirstErrorMessage = form.getFirstErrorMessage

const updateWorkflowDisabledRecipients = (membersSelected) => {
  values.notification_recipient_ids = membersSelected.map(
    ({ user_id: userId }) => userId
  )
}

onBeforeUnmount(() => {
  debouncedUpdateWorkflow.cancel()
})
</script>
