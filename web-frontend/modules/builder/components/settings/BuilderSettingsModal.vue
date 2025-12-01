<template>
  <Modal
    left-sidebar
    left-sidebar-scrollable
    :content-padding="
      settingSelected == null ? true : settingSelected.componentPadding
    "
  >
    <template #sidebar>
      <div class="modal-sidebar__title">
        {{ $t('builderSettingsModal.title') }}
      </div>
      <ul class="modal-sidebar__nav">
        <li v-for="setting in registeredSettings" :key="setting.getType()">
          <a
            v-tooltip="setting.isDeactivatedReason({ workspace }) || null"
            class="modal-sidebar__nav-link"
            :class="{ active: setting === settingSelected }"
            @click="onClick(setting)"
          >
            <i class="modal-sidebar__nav-icon" :class="setting.icon"></i>
            {{ setting.name }}
            <i
              v-if="setting.isDeactivated({ workspace })"
              class="iconoir-lock"
            ></i>
          </a>
          <component
            :is="getDeactivatedModal(setting)[0]"
            v-if="getDeactivatedModal(setting) !== null"
            :ref="`deactivatedClickModal_${setting.getType()}`"
            v-bind="getDeactivatedModal(setting)[1]"
            :name="setting.name"
            :workspace="workspace"
          ></component>
        </li>
      </ul>
    </template>
    <template v-if="settingSelected" #content>
      <component
        :is="settingSelected.component"
        ref="settingSelected"
        :builder="builder"
        :hide-after-create="hideAfterCreate"
        :force-display-form="displaySelectedSettingForm"
        @hide-modal="emitCreatedRecord($event)"
      ></component>
    </template>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import { BuilderApplicationType } from '@baserow/modules/builder/applicationTypes'

export default {
  name: 'BuilderSettingsModal',
  mixins: [modal],
  props: {
    builder: {
      type: Object,
      required: true,
    },
    workspace: {
      type: Object,
      required: true,
    },
    /**
     * If you want the selected setting form to hide the builder settings modal
     * after a record is created, set this to `true`.
     */
    hideAfterCreate: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      settingSelected: null,
      displaySelectedSettingForm: false,
    }
  },
  computed: {
    registeredSettings() {
      return this.$registry.getOrderedList('builderSettings')
    },
  },
  watch: {
    // When the selected setting changes, and we've forcibly displayed
    // the selected setting's form, then reset the display flag so that
    // the next setting doesn't immediately display its form.
    settingSelected(newSetting, oldSetting) {
      if (
        oldSetting &&
        newSetting !== oldSetting &&
        this.displaySelectedSettingForm
      ) {
        this.displaySelectedSettingForm = false
      }
    },
  },
  methods: {
    show(
      selectSettingType = null,
      displaySelectedSettingForm = false,
      ...args
    ) {
      // If we've been instructed to show a specific setting component,
      // then ensure it's displayed first.
      if (selectSettingType) {
        this.settingSelected = this.$registry.get(
          'builderSettings',
          selectSettingType
        )
      }

      // If no `selectSettingType` was provided then choose the first setting.
      if (!this.settingSelected) {
        this.settingSelected = this.registeredSettings[0]
      }

      // If we've been instructed to show the modal, and make the
      // selected setting component's form display, then do so.
      this.displaySelectedSettingForm = displaySelectedSettingForm

      const builderApplicationType = this.$registry.get(
        'application',
        BuilderApplicationType.getType()
      )
      builderApplicationType.loadExtraData(this.builder)

      return modal.methods.show.call(this, ...args)
    },
    /**
     * If this modal is being used with the `hideAfterCreate` prop set to `true`,
     * then once a record has been created, we want to hide the modal, and then
     * emit the newly created record ID so that it can be used by the component
     * implementing this modal.
     * @param createdRecordId - The ID of the newly created record.
     */
    emitCreatedRecord(createdRecordId) {
      this.hide()
      this.$emit('created', createdRecordId)
    },
    onClick(setting) {
      if (setting.isDeactivated({ workspace: this.workspace })) {
        this.$refs[`deactivatedClickModal_${setting.getType()}`][0].show()
      } else {
        this.settingSelected = setting
      }
    },
    isDeactivatedReason(settingType) {
      return settingType.isDeactivatedReason({ workspace: this.workspace })
    },
    getDeactivatedModal(settingType) {
      return settingType.getDeactivatedModal({ workspace: this.workspace })
    },
  },
}
</script>
