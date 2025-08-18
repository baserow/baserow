<template>
  <div class="export-workspace-form">
    <form @submit.prevent="submit">
      <div class="export-workspace-form__section">
        <slot name="select-applications">
          <ApplicationSelector
            :selected-application-ids="values.application_ids"
            :workspace="workspace"
            :disabled="disabled"
            @update="updateSelectedApplications"
          />
        </slot>
      </div>

      <div class="export-workspace-form__section">
        <h4 class="export-workspace-form__section-title">
          {{ $t('exportWorkspaceForm.exportSettingsLabel') }}
        </h4>
        <FormGroup small-label class="export-workspace-form__setting">
          <div class="export-workspace__structure-wrapper">
            <Checkbox v-model="values.only_structure">
              {{ $t('exportWorkspaceForm.onlyStructureLabel') }}
              <HelpIcon
                class="margin-left-1"
                :tooltip="$t('exportWorkspaceForm.onlyStructureDescription')"
                @mousedown.native.stop
                @click.native.stop
              />
            </Checkbox>
          </div>
        </FormGroup>
      </div>

      <slot name="buttons"></slot>
    </form>
  </div>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import { required } from '@vuelidate/validators'
import { useVuelidate } from '@vuelidate/core'
import ApplicationSelector from '@baserow/modules/core/components/export/ApplicationSelector'

export default {
  name: 'ExportWorkspaceForm',
  components: {
    ApplicationSelector,
  },
  mixins: [form],
  props: {
    workspace: {
      type: Object,
      required: true,
    },
    disabled: {
      type: Boolean,
      default: false,
    },
  },
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      values: {
        only_structure: false,
        application_ids: [],
      },
    }
  },
  mounted() {
    this.$nextTick(() => {
      if (this.values.application_ids.length === 0) {
        const allApplications = this.$store.getters[
          'application/getAllOfWorkspace'
        ](this.workspace)
        this.values.application_ids = allApplications.map((app) => app.id)
        this.$emit('update', this.values.application_ids)
      }
    })
  },
  methods: {
    updateSelectedApplications(applicationIds) {
      this.values.application_ids = [...applicationIds]
      this.$emit('update', applicationIds)
    },
  },
  validations() {
    return {
      values: {
        only_structure: {
          required,
        },
      },
    }
  },
}
</script>
