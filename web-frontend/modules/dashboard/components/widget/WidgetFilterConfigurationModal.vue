<template>
  <Modal ref="modal" wide @hidden="modalOpen = false">
    <div v-if="modalOpen" class="dashboard-widget-filters">
      <h2 class="box__title">
        {{ $t('textFilterWidget.filterTarget', { widget: target.title }) }}
      </h2>
      <Alert v-if="unavailableReason" type="warning">{{
        unavailableReason
      }}</Alert>
      <div v-else-if="fieldsLoading" class="loading" />
      <Alert v-else-if="fieldsError" type="error">
        <p>{{ $t('textFilterWidget.fieldsError') }}</p>
        <Button type="secondary" size="small" @click="$emit('retry')">{{
          $t('action.retry')
        }}</Button>
      </Alert>
      <template v-else>
        <Alert
          v-if="hasIncompatibleConditions"
          type="warning"
          class="margin-bottom-2"
          >{{ $t('textFilterWidget.incompatibleConditions') }}</Alert
        >
        <Tabs
          v-model:selected-index="selectedCase"
          class="dashboard-widget-filters__cases"
          header-no-padding
          :tab-items="[
            {
              title: $t('textFilterWidget.withValue'),
              badge: String(link.group?.filters?.length || 0),
              badgeColor: 'neutral',
            },
            {
              title: $t('textFilterWidget.whenEmpty'),
              badge: String(
                link.empty_behavior === 'apply_alternative'
                  ? link.alternative_group?.filters?.length || 0
                  : 0
              ),
              badgeColor: 'neutral',
            },
          ]"
        />
        <TargetFilterGroup
          v-if="selectedCase === 0"
          :key="`${target.id}-normal`"
          :group="link.group"
          :fields="fields"
          :dashboard="dashboard"
          :owner="widget"
          @update="$emit('update', { ...link, group: $event })"
        />
        <template v-else>
          <Dropdown
            class="dashboard-widget-filters__empty-behavior"
            :aria-label="$t('textFilterWidget.emptyBehavior')"
            :model-value="link.empty_behavior"
            @update:model-value="updateEmptyBehavior"
          >
            <DropdownItem
              v-for="policy in ['apply_nothing', 'apply_alternative']"
              :key="policy"
              :name="$t(`textFilterWidget.${policy}`)"
              :value="policy"
            />
          </Dropdown>
          <div
            v-if="link.empty_behavior === 'apply_alternative'"
            class="dashboard-widget-filters__alternative"
          >
            <TargetFilterGroup
              :key="`${target.id}-alternative`"
              :group="link.alternative_group || emptyGroup()"
              :fields="fields"
              :dashboard="dashboard"
              :owner="widget"
              @update="$emit('update', { ...link, alternative_group: $event })"
            />
          </div>
        </template>
        <WidgetFilterGroups
          :groups="readonlyGroups"
          :dashboard="dashboard"
          :fields="fields"
          :filter-type="source?.filter_type || 'AND'"
          :title="$t('textFilterWidget.otherConditions')"
        />
      </template>
      <div class="dashboard-widget-filters__footer">
        <Button type="secondary" @click="hide()">{{
          $t('action.close')
        }}</Button>
      </div>
    </div>
  </Modal>
</template>

<script setup>
import TargetFilterGroup from '@baserow/modules/dashboard/components/widget/TargetFilterGroup'
import WidgetFilterGroups from '@baserow/modules/dashboard/components/widget/WidgetFilterGroups'

const props = defineProps({
  widget: { type: Object, required: true },
  dashboard: { type: Object, required: true },
  target: { type: Object, required: true },
  source: { type: Object, default: null },
  fieldsLoading: Boolean,
  fieldsError: Boolean,
  hasIncompatibleConditions: Boolean,
  unavailableReason: { type: String, default: null },
  link: { type: Object, required: true },
  fields: { type: Array, required: true },
  readonlyGroups: { type: Array, required: true },
})
const emit = defineEmits(['update', 'retry'])

const selectedCase = ref(0)
const modal = ref(null)
const modalOpen = ref(false)
const emptyGroup = () => ({
  filters: [],
  filter_groups: [],
  filter_type: 'AND',
})
const updateEmptyBehavior = (empty_behavior) =>
  emit('update', {
    ...props.link,
    empty_behavior,
    ...(empty_behavior === 'apply_alternative'
      ? { alternative_group: props.link.alternative_group || emptyGroup() }
      : {}),
  })
const show = () => {
  selectedCase.value = 0
  modalOpen.value = true
  modal.value.show()
}
const hide = () => modal.value.hide()

defineExpose({ show, hide })
</script>
