<template>
  <div v-if="canCreateWidget || canCreateFilter" class="dashboard-add-element">
    <Button
      ref="trigger"
      class="dashboard-add-element__trigger"
      icon="iconoir-plus"
      :loading="loading"
      :aria-expanded="open"
      @click="toggle"
      >{{ $t('dashboardAddElement.addNew') }}</Button
    >
    <Context
      ref="context"
      class="dashboard-add-element__context"
      @shown="focusFirstOption"
      @hidden="open = false"
      @keydown.esc.prevent.stop="close"
    >
      <ul class="context__menu">
        <li v-if="canCreateWidget" class="context__menu-item">
          <button
            ref="widgetOption"
            type="button"
            class="context__menu-item-link context__menu-item-link--with-desc dashboard-add-element__option"
            data-testid="create-dashboard-widget"
            :disabled="loading"
            @click="createWidget"
          >
            <span class="context__menu-item-title">
              <i class="context__menu-item-icon iconoir-graph-up" />
              {{ $t('dashboardAddElement.widget') }}
            </span>
            <span
              class="context__menu-item-description context__menu-item-description--offset"
              >{{ $t('dashboardAddElement.widgetDescription') }}</span
            >
          </button>
        </li>
        <li v-if="canCreateFilter" class="context__menu-item">
          <button
            ref="filterOption"
            type="button"
            class="context__menu-item-link context__menu-item-link--with-desc dashboard-add-element__option"
            data-testid="create-dashboard-filter"
            :disabled="loading"
            @click="createFilter"
          >
            <span class="context__menu-item-title">
              <i class="context__menu-item-icon iconoir-filter" />
              {{ $t('dashboardAddElement.filter') }}
            </span>
            <span
              class="context__menu-item-description context__menu-item-description--offset"
              >{{ $t('dashboardAddElement.filterDescription') }}</span
            >
          </button>
        </li>
      </ul>
    </Context>
    <CreateWidgetModal
      v-if="canCreateWidget"
      ref="createWidgetModal"
      :dashboard="dashboard"
      :loading="loading"
      @widget-variation-selected="$emit('widget-variation-selected', $event)"
    />
  </div>
</template>

<script setup>
import { computed, nextTick, ref } from 'vue'
import { useNuxtApp } from '#app'
import CreateWidgetModal from '@baserow/modules/dashboard/components/CreateWidgetModal'

const props = defineProps({
  dashboard: { type: Object, required: true },
  loading: { type: Boolean, default: false },
})
const emit = defineEmits(['widget-variation-selected', 'create-filter'])
const { $hasPermission } = useNuxtApp()
const canCreate = (operation) =>
  $hasPermission(operation, props.dashboard, props.dashboard.workspace.id)
const canCreateWidget = computed(() => canCreate('dashboard.create_widget'))
const canCreateFilter = computed(() => canCreate('dashboard.create_filter'))
const context = ref(null)
const trigger = ref(null)
const widgetOption = ref(null)
const filterOption = ref(null)
const createWidgetModal = ref(null)
const open = ref(false)

function toggle(event) {
  if (!props.loading) {
    context.value.toggle(event.currentTarget, 'bottom', 'right', 8)
  }
}

async function focusFirstOption() {
  open.value = true
  await nextTick()
  const firstOption = widgetOption.value || filterOption.value
  firstOption?.focus()
}

function close() {
  context.value.hide()
  trigger.value.$el.focus()
}

function createWidget() {
  if (!props.loading) {
    context.value.hide()
    createWidgetModal.value.show()
  }
}

function createFilter() {
  if (!props.loading) {
    close()
    emit('create-filter')
  }
}
</script>
