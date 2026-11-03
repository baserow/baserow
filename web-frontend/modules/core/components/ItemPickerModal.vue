<template>
  <Modal ref="modal" class="item-picker-modal" @show="focusSearch">
    <h2 class="box__title">{{ title }}</h2>
    <FormInput
      ref="searchInput"
      v-model="search"
      class="item-picker-modal__search"
      size="large"
      :placeholder="searchPlaceholder"
      icon-left="iconoir-search"
    />
    <div class="item-picker-modal__groups">
      <Expandable
        v-for="group in filteredGroups"
        :key="group.id"
        class="item-picker-modal__group"
        :default-expanded="!group.initiallyCollapsed"
        :force-expanded="search.trim() ? true : null"
      >
        <template #header="{ toggle, expanded }">
          <button
            type="button"
            class="item-picker-modal__group-title"
            :aria-expanded="expanded"
            @click="toggle"
          >
            {{ group.label }}
            <i
              aria-hidden="true"
              :class="
                expanded ? 'iconoir-nav-arrow-down' : 'iconoir-nav-arrow-right'
              "
            />
          </button>
        </template>
        <template #default>
          <div class="item-picker-modal__items">
            <slot name="items" :items="group.items" />
          </div>
        </template>
      </Expandable>
      <p v-if="!filteredGroups.length" class="item-picker-modal__empty">
        {{ $t('itemPickerModal.noResults') }}
      </p>
    </div>
  </Modal>
</template>

<script setup>
import { computed, nextTick, ref } from 'vue'
import Modal from '@baserow/modules/core/components/Modal'
import FormInput from '@baserow/modules/core/components/FormInput'
import Expandable from '@baserow/modules/core/components/Expandable'
import { isSubstringOfStrings } from '@baserow/modules/core/utils/string'

const props = defineProps({
  title: { type: String, required: true },
  searchPlaceholder: { type: String, required: true },
  groups: { type: Array, required: true },
})

const modal = ref(null)
const searchInput = ref(null)
const search = ref('')

const filteredGroups = computed(() =>
  props.groups
    .map((group) => ({
      ...group,
      items: group.items.filter((item) =>
        isSubstringOfStrings([item.name, item.description || ''], search.value)
      ),
    }))
    .filter((group) => group.items.length > 0)
)

async function focusSearch() {
  await nextTick()
  searchInput.value?.focus()
}

function show(...args) {
  modal.value.show(...args)
}

function hide(...args) {
  modal.value.hide(...args)
}

function toggleModal(...args) {
  modal.value.toggle(...args)
}

function getTeleportedElement() {
  return modal.value.getTeleportedElement()
}

defineExpose({ show, hide, toggle: toggleModal, getTeleportedElement })
</script>
