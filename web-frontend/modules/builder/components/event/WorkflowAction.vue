<template>
  <SidebarExpandable :force-expanded="expanded" @toggle="$emit('toggle')">
    <template #title>
      <Icon v-if="workflowActionType.icon" :icon="workflowActionType.icon" />
      <img
        v-else-if="workflowActionType.image"
        alt=""
        class="workflow-action__image"
        :src="workflowActionType.image"
      />
      <span>{{ workflowActionType.label }}</span>
      <Icon
        v-if="errorMessage"
        :key="errorMessage"
        v-tooltip="errorMessage"
        tooltip-position="bottom-left"
        icon="iconoir-warning-circle"
        size="medium"
        type="error"
      />
    </template>
    <template v-if="workflowActionType.form" #default>
      <component
        :is="workflowActionType.form"
        ref="actionForm"
        :workflow-action="workflowAction"
        :default-values="workflowAction"
        @values-changed="updateWorkflowAction($event)"
      />
      <div v-if="isServiceWorkflowAction" class="workflow-action__payload">
        <SampleDataViewer
          v-if="sampleData"
          :sample-data="sampleData"
          :is-error="isErrorSample"
          :modal-title="sampleDataModalTitle"
          :modal-subtitle="$t('workflowAction.sampleDataModalSubTitle')"
        />
        <Alert v-else type="info-neutral" class="margin-bottom-0">
          <p>{{ $t('workflowAction.testActionDescription') }}</p>
        </Alert>
      </div>
    </template>
    <template #footer>
      <ButtonText icon="iconoir-bin" @click="$emit('delete')">
        {{ $t('action.delete') }}
      </ButtonText>
    </template>
  </SidebarExpandable>
</template>

<script>
import SidebarExpandable from '@baserow/modules/builder/components/SidebarExpandable.vue'
import SampleDataViewer from '@baserow/modules/core/components/SampleDataViewer'
import _ from 'lodash'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { mapActions } from 'vuex'
import applicationContext from '@baserow/modules/builder/mixins/applicationContext'

export default {
  name: 'WorkflowAction',
  components: { SampleDataViewer, SidebarExpandable },
  mixins: [applicationContext],
  inject: ['workspace', 'builder', 'elementPage', 'mode'],
  props: {
    availableWorkflowActionTypes: {
      type: Array,
      required: true,
    },
    workflowAction: {
      type: Object,
      required: false,
      default: null,
    },
    element: {
      type: Object,
      required: true,
    },
    expanded: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['toggle', 'delete'],
  data() {
    return {
      loading: false,
    }
  },
  computed: {
    workflowActionType() {
      return this.availableWorkflowActionTypes.find(
        (workflowActionType) =>
          workflowActionType.getType() === this.workflowAction.type
      )
    },
    errorMessage() {
      return this.workflowActionType.getErrorMessage(
        this.workflowAction,
        this.applicationContext
      )
    },
    isServiceWorkflowAction() {
      return Boolean(this.workflowAction.service)
    },
    serviceSampleData() {
      return this.workflowAction.service?.sample_data || null
    },

    sampleData() {
      const sample = this.serviceSampleData

      if (sample?._error) {
        return sample._error
      }
      if (this.workflowActionType.returnsList && sample?.data) {
        return sample.data.results
      }
      return sample?.data || null
    },
    isErrorSample() {
      return Boolean(this.serviceSampleData?._error)
    },
    sampleDataModalTitle() {
      return this.$t('workflowAction.sampleDataModalTitle', {
        actionLabel: this.workflowActionType.label,
      })
    },
  },
  created() {
    // Reset the form when the workflow action's realtime version advances (an
    // undo/redo or another user's change). Comparing the version — rather than just
    // reading the `viaRealtime` flag, which stays set until the next local edit —
    // ensures we only reset on a genuinely new realtime event. Runs post-flush so the
    // form's `defaultValues` reflect the change first.
    this.$watch(
      () => [this.workflowAction?.id, this.workflowAction?._?.realtimeVersion],
      ([id, version], [oldId, oldVersion]) => {
        if (
          id === oldId &&
          version !== oldVersion &&
          this.workflowAction?._?.viaRealtime
        ) {
          this.$refs.actionForm?.reset?.(true)
        }
      },
      { flush: 'post' }
    )
  },
  methods: {
    ...mapActions({
      actionUpdateWorkflowAction: 'builderWorkflowAction/updateDebounced',
    }),
    async updateWorkflowAction(values) {
      if (this.$refs.actionForm && !this.$refs.actionForm.isFormValid()) {
        return
      }

      const differences = Object.fromEntries(
        Object.entries(values).filter(
          ([key, value]) => !_.isEqual(value, this.workflowAction[key])
        )
      )

      // In this case there weren't any actual changes
      if (Object.keys(differences).length === 0) {
        return
      }
      if (values.type) {
        this.loading = true
      }

      try {
        await this.actionUpdateWorkflowAction({
          page: this.elementPage,
          workflowAction: this.workflowAction,
          values: differences,
        })
      } catch (error) {
        this.$refs.actionForm?.reset()
        notifyIf(error)
      }

      this.loading = false
    },
  },
}
</script>
