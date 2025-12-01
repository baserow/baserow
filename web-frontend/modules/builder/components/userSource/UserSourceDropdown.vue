<template>
  <div>
    <Dropdown
      :value="value"
      fixed-items
      show-footer
      :show-search="false"
      @input="$emit('input', $event)"
    >
      <DropdownItem
        v-for="userSource in userSources"
        :key="userSource.id"
        :name="userSource.name"
        :value="userSource.id"
      />
      <template #emptyState>
        <slot name="emptyState">
          {{ $t('userSourceDropdown.noUserSources') }}
        </slot>
      </template>
      <template #footer>
        <a class="select__footer-button" @click="openUserSettings">
          <i class="iconoir-plus"></i>
          {{ $t('userSourceDropdown.addUserSource') }}
        </a>
        <BuilderSettingsModal
          ref="userSourcesSettingsModal"
          hide-after-create
          :builder="builder"
          :workspace="workspace"
          @created="$emit('input', $event)"
        />
      </template>
    </Dropdown>
  </div>
</template>

<script>
import BuilderSettingsModal from '@baserow/modules/builder/components/settings/BuilderSettingsModal'
import { UserSourcesBuilderSettingsType } from '@baserow/modules/builder/builderSettingTypes'

export default {
  name: 'UserSourceDropdown',
  components: { BuilderSettingsModal },
  inject: ['workspace'],
  props: {
    value: {
      type: Number,
      required: false,
      default: null,
    },
    builder: {
      type: Object,
      required: true,
    },
    userSources: {
      type: Array,
      required: true,
    },
  },
  methods: {
    openUserSettings() {
      this.$refs.userSourcesSettingsModal.show(
        UserSourcesBuilderSettingsType.getType(),
        true
      )
    },
  },
}
</script>
