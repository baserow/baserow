<template>
  <Context ref="contextRef" class="template-icon-select-context" @shown="shown">
    <SelectSearch
      ref="searchRef"
      v-model="search"
      :placeholder="$t('templateIconSelectContext.search')"
    />
    <div
      v-if="icons.length > 0"
      v-auto-overflow-scroll
      class="template-icon-select-context__icons"
    >
      <button
        v-for="icon in icons"
        :key="icon"
        type="button"
        class="template-icon-select-context__icon"
        :class="{
          'template-icon-select-context__icon--active': icon === active,
        }"
        :title="getIconName(icon)"
        @click="select(icon)"
      >
        <i :class="icon"></i>
      </button>
    </div>
    <div v-else class="template-icon-select-context__empty">
      {{ $t('templateIconSelectContext.noResults') }}
    </div>
  </Context>
</template>

<script setup>
import { computed, nextTick, ref } from 'vue'

import { TEMPLATE_ICONS } from '@baserow/modules/core/utils/templateIcons'

defineProps({
  // The icon that is currently picked.
  active: {
    type: String,
    default: null,
  },
})

const emit = defineEmits(['selected'])

const contextRef = ref(null)
const searchRef = ref(null)
const search = ref('')

// The name of `iconoir-light-bulb-on` is `light bulb on`.
function getIconName(icon) {
  return icon.replace(/^iconoir-/, '').replaceAll('-', ' ')
}

const icons = computed(() => {
  const query = search.value.trim().toLowerCase()
  return TEMPLATE_ICONS.filter((icon) => getIconName(icon).includes(query))
})

async function shown() {
  search.value = ''
  await nextTick()
  searchRef.value?.$el.querySelector('input')?.focus()
}

function select(icon) {
  emit('selected', icon)
  contextRef.value.hide()
}

function toggle(...args) {
  contextRef.value.toggle(...args)
}

function hide() {
  contextRef.value.hide()
}

defineExpose({ toggle, hide })
</script>
