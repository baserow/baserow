<template>
  <Modal
    left-sidebar
    left-sidebar-scrollable
    :content-padding="
      settingSelected == null ? true : settingSelected.componentPadding
    "
  >
    <template #sidebar>
      <div class="modal-sidebar__head">
        <div class="modal-sidebar__head-name">
          {{ $t('automationSettingsModal.title') }}
        </div>
      </div>
      <ul class="modal-sidebar__nav">
        <li v-for="setting in registeredSettings" :key="setting.getType()">
          <a
            class="modal-sidebar__nav-link"
            :class="{ active: setting === settingSelected }"
            @click="settingSelected = setting"
          >
            <i class="modal-sidebar__nav-icon" :class="setting.icon"></i>
            {{ setting.name }}
          </a>
        </li>
      </ul>
    </template>
    <template v-if="settingSelected" #content>
      <component
        :is="settingSelected.component"
        ref="settingSelected"
        :automation="automation"
        :default-values="automation"
        :hide-after-create="hideAfterCreate"
        :force-display-form="displaySelectedSettingForm"
        @hide-modal="emitCreatedRecord($event)"
      ></component>
    </template>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import { defineComponent, ref, computed, watch, getCurrentInstance } from 'vue'
import { useContext } from '@nuxtjs/composition-api'

export default defineComponent({
  name: 'AutomationSettingsModal',
  mixins: [modal],
  props: {
    automation: {
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

  setup(props, { emit }) {
    const instance = getCurrentInstance()
    const { app } = useContext()

    const settingSelected = ref(null)
    const displaySelectedSettingForm = ref(false)

    const registeredSettings = computed(() => {
      return app.$registry
        .getOrderedList('automationSettings')
        .filter((setting) => !setting.isDeactivated())
    })

    // Watch for changes in the selected setting
    watch(settingSelected, (newSetting, oldSetting) => {
      if (
        oldSetting &&
        newSetting !== oldSetting &&
        displaySelectedSettingForm.value
      ) {
        displaySelectedSettingForm.value = false
      }
    })

    // Method to emit the created record and hide the modal
    const emitCreatedRecord = (createdRecordId) => {
      instance.proxy.hide()
      emit('created', createdRecordId)
    }

    return {
      registeredSettings,
      emitCreatedRecord,
    }
  },
  data() {
    return {
      settingSelected: null,
      displaySelectedSettingForm: false,
    }
  },
  methods: {
    /**
     * Override show method from the modal mixin to handle setting selection.
     */
    show(
      selectSettingType = null,
      displaySelectedSettingFormValue = false,
      ...args
    ) {
      // If we've been instructed to show a specific setting component,
      // then ensure it's displayed first.
      if (selectSettingType) {
        this.settingSelected = this.$registry.get(
          'automationSettings',
          selectSettingType
        )
      }

      // If no `selectSettingType` was provided then choose the first setting.
      if (!this.settingSelected) {
        this.settingSelected = this.registeredSettings[0]
      }

      // If we've been instructed to show the modal, and make the
      // selected setting component's form display, then do so.
      this.displaySelectedSettingForm = displaySelectedSettingFormValue

      // Call the original show method from the mixin
      return modal.methods.show.call(this, ...args)
    },
  },
})
</script>
