<template>
  <Modal left-sidebar left-sidebar-scrollable>
    <template #sidebar>
      <div class="modal-sidebar__title">
        {{ page.name }}
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
      <component :is="settingSelected.component"></component>
    </template>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'

export default {
  name: 'PageSettingsModal',
  mixins: [modal],
  props: {
    page: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      settingSelected: null,
    }
  },
  computed: {
    registeredSettings() {
      return this.$registry.getOrderedList('pageSettings')
    },
  },
  methods: {
    show(...args) {
      if (!this.settingSelected) {
        this.settingSelected = this.registeredSettings[0]
      }
      return modal.methods.show.call(this, ...args)
    },
  },
}
</script>
