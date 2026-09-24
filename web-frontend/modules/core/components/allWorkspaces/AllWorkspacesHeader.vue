<template>
  <div class="all-workspaces__header">
    <h1 class="all-workspaces__title">
      {{
        searchActive
          ? $t('allWorkspaces.searchResults')
          : $t('allWorkspaces.title')
      }}
    </h1>

    <div class="all-workspaces__search">
      <FormInput
        ref="searchInput"
        :model-value="search"
        :placeholder="$t('allWorkspaces.searchPlaceholder')"
        icon-left="iconoir-search"
        can-clear
        @update:model-value="$emit('update:search', $event)"
      ></FormInput>
      <ClientOnly>
        <div v-if="search === ''" class="all-workspaces__search-shortcut">
          <kbd>{{ modifierKey }}</kbd
          ><kbd>K</kbd>
        </div>
        <template #fallback>
          <div class="all-workspaces__search-shortcut">
            <kbd>Ctrl</kbd><kbd>K</kbd>
          </div>
        </template>
      </ClientOnly>
    </div>

    <Dropdown
      class="all-workspaces__items-filter"
      :model-value="selectedTypes"
      :show-search="false"
      multiple
      @update:model-value="$emit('update:selectedTypes', $event)"
    >
      <template #selectedValue>
        <span class="dropdown__selected-text">{{ itemsFilterLabel }}</span>
      </template>
      <template #defaultValue>
        <span class="dropdown__selected-text">{{ itemsFilterLabel }}</span>
      </template>
      <DropdownItem
        v-for="applicationType in applicationTypes"
        :key="applicationType.getType()"
        :name="applicationType.getName()"
        :value="applicationType.getType()"
        :icon="applicationType.iconClass"
      ></DropdownItem>
    </Dropdown>

    <span ref="viewContextLink">
      <ButtonIcon
        type="secondary"
        icon="baserow-icon-more-vertical"
        @click="$refs.viewContext.toggle($refs.viewContextLink)"
      ></ButtonIcon>
    </span>
    <Context ref="viewContext">
      <ul class="context__menu context__menu--can-be-active">
        <li class="context__menu-item">
          <a
            class="context__menu-item-link"
            :class="{ active: viewMode === 'expanded' }"
            @click="setViewMode('expanded')"
          >
            {{ $t('allWorkspaces.expandedView') }}
            <i
              v-if="viewMode === 'expanded'"
              class="context__menu-active-icon iconoir-check"
            ></i>
          </a>
        </li>
        <li class="context__menu-item">
          <a
            class="context__menu-item-link"
            :class="{ active: viewMode === 'compact' }"
            @click="setViewMode('compact')"
          >
            {{ $t('allWorkspaces.compactView') }}
            <i
              v-if="viewMode === 'compact'"
              class="context__menu-active-icon iconoir-check"
            ></i>
          </a>
        </li>
        <li class="context__menu-item context__menu-item--with-separator">
          <a
            class="context__menu-item-link"
            @click="($emit('collapse-all'), $refs.viewContext.hide())"
          >
            {{ $t('allWorkspaces.collapseAll') }}
          </a>
        </li>
        <li class="context__menu-item">
          <a
            class="context__menu-item-link"
            @click="($emit('expand-all'), $refs.viewContext.hide())"
          >
            {{ $t('allWorkspaces.expandAll') }}
          </a>
        </li>
      </ul>
    </Context>

    <div class="all-workspaces__header-divider"></div>

    <template v-if="$hasPermission('create_workspace')">
      <Button
        type="primary"
        icon="iconoir-plus"
        tag="a"
        @click="$refs.createWorkspaceModal.show()"
        >{{ $t('allWorkspaces.createWorkspace') }}</Button
      >
      <CreateWorkspaceModal ref="createWorkspaceModal"></CreateWorkspaceModal>
    </template>
  </div>
</template>

<script>
import CreateWorkspaceModal from '@baserow/modules/core/components/workspace/CreateWorkspaceModal'
import { isMac } from '@baserow/modules/core/utils/events'
import { isTypeFilterActive } from '@baserow/modules/core/utils/allWorkspacesSearch'

export default {
  name: 'AllWorkspacesHeader',
  components: { CreateWorkspaceModal },
  props: {
    search: {
      type: String,
      required: true,
    },
    selectedTypes: {
      type: Array,
      required: true,
    },
    viewMode: {
      type: String,
      required: true,
    },
  },
  emits: [
    'update:search',
    'update:selectedTypes',
    'update:viewMode',
    'collapse-all',
    'expand-all',
  ],
  computed: {
    searchActive() {
      return this.search.trim() !== ''
    },
    applicationTypes() {
      return this.$registry.getOrderedList('application')
    },
    modifierKey() {
      return isMac() ? '⌘' : 'Ctrl'
    },
    itemsFilterLabel() {
      if (
        !isTypeFilterActive(this.selectedTypes, this.applicationTypes.length)
      ) {
        return this.$t('allWorkspaces.allItems')
      }
      return this.$t('allWorkspaces.itemsSelected', {
        count: this.selectedTypes.length,
      })
    },
  },
  methods: {
    focusSearch() {
      this.$refs.searchInput.focus()
    },
    setViewMode(viewMode) {
      this.$emit('update:viewMode', viewMode)
      this.$refs.viewContext.hide()
    },
  },
}
</script>
