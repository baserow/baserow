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
import _ from 'lodash'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { mapActions } from 'vuex'
import applicationContext from '@baserow/modules/builder/mixins/applicationContext'

export default {
  name: 'WorkflowAction',
  components: { SidebarExpandable },
  mixins: [applicationContext],
  inject: ['builder', 'elementPage', 'mode'],
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
  data() {
    return { loading: false }
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
