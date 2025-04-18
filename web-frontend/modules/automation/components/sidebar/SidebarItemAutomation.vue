<template>
  <li class="tree__sub" :class="{ active: workflow?._?.selected }">
    <a
      class="tree__sub-link"
      :title="workflow.name"
      :href="resolveWorkflowHref(automation, workflow)"
      @mousedown.prevent
      @click.prevent="selectWorkflow(automation, workflow)"
    >
      <Editable
        ref="rename"
        :value="workflow.name"
        class="side-bar-automation__link-text"
        @change="renameWorkflow(automation, workflow, $event)"
      ></Editable>
    </a>

    <a
      v-show="!automation._.loading"
      v-if="showOptions"
      class="tree__options"
      @click="$refs.context.toggle($event.currentTarget, 'bottom', 'right', 0)"
      @mousedown.stop
    >
      <i class="baserow-icon-more-vertical"></i>
    </a>

    <Context ref="context" overflow-scroll max-height-if-outside-viewport>
      <div class="context__menu-title">
        {{ workflow.name }} ({{ workflow.id }})
      </div>
      <ul class="context__menu">
        <li
          v-if="
            $hasPermission(
              'automation.workflow.update',
              workflow,
              automation.workspace.id
            )
          "
          class="context__menu-item"
        >
          <a class="context__menu-item-link" @click="enableRename()">
            <i class="context__menu-item-icon iconoir-edit-pencil"></i>
            {{ $t('action.rename') }}
          </a>
        </li>
        <li
          v-if="
            $hasPermission(
              'automation.workflow.duplicate',
              workflow,
              automation.workspace.id
            )
          "
          class="context__menu-item"
        >
          <a
            :class="{
              'context__menu-item-link--loading': duplicateLoading,
              disabled: deleteLoading || duplicateLoading,
            }"
            class="context__menu-item-link"
            @click="duplicateWorkflow()"
          >
            <i class="context__menu-item-icon iconoir-copy"></i>
            {{ $t('action.duplicate') }}
          </a>
        </li>
        <li
          v-if="
            $hasPermission(
              'automation.workflow.delete',
              workflow,
              automation.workspace.id
            )
          "
          class="context__menu-item context__menu-item--with-separator"
        >
          <a
            :class="{ 'context__menu-item-link--loading': deleteLoading }"
            class="context__menu-item-link context__menu-link--delete"
            @click="deleteWorkflow()"
          >
            <i class="context__menu-item-icon iconoir-bin"></i>
            {{ $t('action.delete') }}
          </a>
        </li>
      </ul>
    </Context>
  </li>
</template>

<script>
import { notifyIf } from '@baserow/modules/core/utils/error'
import { mapGetters } from 'vuex'

export default {
  name: 'SidebarItemAutomation',
  props: {
    automation: {
      type: Object,
      required: true,
    },
    workflow: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      deleteLoading: false,
      duplicateLoading: false,
    }
  },
  computed: {
    showOptions() {
      return (
        this.$hasPermission(
          'automation.workflow.run_export',
          this.workflow,
          this.automation.workspace.id
        ) ||
        this.$hasPermission(
          'automation.workflow.update',
          this.workflow,
          this.automation.workspace.id
        ) ||
        this.$hasPermission(
          'automation.workflow.duplicate',
          this.workflow,
          this.automation.workspace.id
        )
      )
    },
    ...mapGetters({ duplicateJob: 'automationWorkflow/getDuplicateJob' }),
  },
  watch: {
    'duplicateJob.state'(newState) {
      if (['finished', 'failed'].includes(newState)) {
        this.duplicateLoading = false
      }
    },
  },
  methods: {
    setLoading(automation, value) {
      this.$store.dispatch('application/setItemLoading', {
        application: automation,
        value,
      })
    },
    selectWorkflow(automation, workflow) {
      this.setLoading(automation, true)
      this.$nuxt.$router.push(
        {
          name: 'automation-workflow',
          params: {
            automationId: automation.id,
            workflowId: workflow.id,
          },
        },
        () => {
          this.setLoading(automation, false)
        },
        () => {
          this.setLoading(automation, false)
        }
      )
    },
    resolveWorkflowHref(automation, workflow) {
      const props = this.$nuxt.$router.resolve({
        name: 'automation-workflow',
        params: {
          automationId: automation.id,
          workflowId: workflow.id,
        },
      })

      return props.href
    },
    enableRename() {
      this.$refs.context.hide()
      this.$refs.rename.edit()
    },
    async renameWorkflow(automation, workflow, event) {
      this.setLoading(automation, true)
      try {
        await this.$store.dispatch('automationWorkflow/update', {
          automation,
          workflow,
          values: {
            name: event.value,
          },
        })
      } catch (error) {
        this.$refs.rename.set(event.oldValue)
        notifyIf(error, 'automationWorkflow')
      }

      this.setLoading(automation, false)
    },
    async deleteWorkflow() {
      this.deleteLoading = true

      try {
        await this.$store.dispatch('automationWorkflow/delete', {
          automation: this.automation,
          workflow: this.workflow,
        })
      } catch (error) {
        notifyIf(error, 'automationWorkflow')
      }

      this.deleteLoading = false
    },
    async duplicateWorkflow() {
      if (this.duplicateLoading) {
        return
      }

      this.duplicateLoading = true

      try {
        await this.$store.dispatch('automationWorkflow/duplicate', {
          workflow: this.workflow,
        })
      } catch (error) {
        notifyIf(error, 'automationWorkflow')
      }

      this.$refs.context.hide()
    },
  },
}
</script>
