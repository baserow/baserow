<template>
  <ModalV2
    left-sidebar
    :content-padding="
      settingSelected == null ? true : settingSelected.componentPadding
    "
    :header="hasTitle"
    :footer="hasFooter"
  >
    <template v-if="hasTitle" #header-content>
      <h2>{{ title }}</h2>
    </template>

    <template #sidebar-content>
      <div class="modal-sidebar__head">
        <div class="modal-sidebar__head-name">
          {{ $t('builderSettingsModal.title') }}
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
        ref="settingComponent"
        :builder="builder"
        @edit-user-source="$refs.modalFooterComponent.setEditMode()"
        @domain-form-loading="loading = $event"
      ></component>
    </template>

    <template v-if="hasFooter" #footer-content>
      <component
        :is="getFooterComponent()"
        ref="modalFooterComponent"
        :loading="loading"
        @show-domains-form="$refs.settingComponent.showForm()"
        @hide-domains-form="$refs.settingComponent.hideForm()"
        @create-domain="$refs.settingComponent.submitForm()"
        @show-user-source-form="handleShowUserSourceForm"
        @create-user-source="$refs.settingComponent.submitForm()"
        @edit-user-source="$refs.settingComponent.submitForm()"
        @hide-user-source-form="$refs.settingComponent.hideForm()"
      ></component>
    </template>
  </ModalV2>
</template>

<script>
import modalv2 from '@baserow/modules/core/mixins/modalv2'
import { BuilderApplicationType } from '@baserow/modules/builder/applicationTypes'

export default {
  name: 'BuilderSettingsModal',
  mixins: [modalv2],
  props: {
    builder: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      settingSelected: null,
      title: '',
      componentName: '',
      displayUserSourceForm: false,
      loading: false,
    }
  },
  computed: {
    registeredSettings() {
      return this.$registry.getOrderedList('builderSettings')
    },
    hasTitle() {
      return this.title !== ''
    },
    hasFooter() {
      return (
        this.componentName === 'UserSourceSettings' ||
        this.componentName === 'DomainsSettings'
      )
    },
  },
  watch: {
    settingSelected(newSetting) {
      this.$nextTick(() => {
        this.title = this.$refs.settingComponent?.getTitle()
        this.componentName = newSetting?.component.name
      })
    },
  },
  methods: {
    show(...args) {
      if (!this.settingSelected) {
        this.settingSelected = this.registeredSettings[0]
      }

      const builderApplicationType = this.$registry.get(
        'application',
        BuilderApplicationType.getType()
      )
      builderApplicationType.loadExtraData(this.builder)

      return modalv2.methods.show.call(this, ...args)
    },
    handleShowUserSourceForm() {
      this.$refs.settingComponent.showForm()
    },
    getFooterComponent() {
      return this.$refs.settingComponent?.getFooterComponent() || null
    },
  },
}
</script>
