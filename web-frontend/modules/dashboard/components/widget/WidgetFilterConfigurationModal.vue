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
        <h3 class="dashboard-widget-filters__title">{{ widget.title }}</h3>
        <SegmentControl
          v-model:active-index="selectedCase"
          class="dashboard-widget-filters__cases"
          :segments="[
            { label: $t('textFilterWidget.withValue') },
            { label: $t('textFilterWidget.whenEmpty') },
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
        <div
          v-if="readonlyGroups.length"
          class="dashboard-widget-filters__operator"
        >
          <Badge size="small">{{ source.filter_type }}</Badge>
        </div>
        <section
          v-if="readonlyGroups.length"
          class="dashboard-widget-filters__other"
        >
          <div class="dashboard-widget-filters__other-header">
            <h3 class="dashboard-widget-filters__title">
              {{ $t('textFilterWidget.otherConditions') }}
            </h3>
            <Badge size="small">{{ otherConditionCount }}</Badge>
          </div>
          <template
            v-for="(context, index) in readonlyGroups"
            :key="context.key"
          >
            <div v-if="index" class="dashboard-widget-filters__operator">
              <Badge size="small">{{ source.filter_type }}</Badge>
            </div>
            <Expandable
              :default-expanded="readonlyGroups.length === 1"
              card
              toggle-on-click
              class="dashboard-widget-filters__source"
            >
              <template #header="{ toggle, expanded }">
                <div class="dashboard-widget-filters__source-header">
                  <ButtonText
                    type="secondary"
                    class="dashboard-widget-filters__source-toggle"
                    :icon="
                      expanded
                        ? 'iconoir-nav-arrow-down'
                        : 'iconoir-nav-arrow-right'
                    "
                    :aria-expanded="expanded"
                    :title="context.title"
                    @click.stop="toggle"
                    >{{ context.title }}</ButtonText
                  >
                  <HelpIcon
                    icon="iconoir-lock"
                    class="dashboard-widget-filters__source-lock"
                    :tooltip="
                      context.owner
                        ? $t('textFilterWidget.editFilterConditions', {
                            filter: context.title,
                          })
                        : $t('textFilterWidget.editWidgetConditions')
                    "
                    @click.stop
                  />
                </div>
              </template>
              <div class="dashboard-widget-filters__source-detail">
                <FormGroup
                  v-if="context.group.filters.length"
                  small-label
                  :label="
                    context.owner ? $t('textFilterWidget.withValue') : null
                  "
                  required
                >
                  <TargetFilterGroup
                    :group="context.group"
                    :fields="fields"
                    :dashboard="dashboard"
                    :owner="context.owner"
                    read-only
                  />
                </FormGroup>
                <FormGroup
                  v-if="context.alternativeGroup"
                  small-label
                  :label="$t('textFilterWidget.whenEmpty')"
                  class="margin-top-2"
                  required
                >
                  <TargetFilterGroup
                    :group="context.alternativeGroup"
                    :fields="fields"
                    :dashboard="dashboard"
                    :owner="context.owner"
                    read-only
                  />
                </FormGroup>
              </div>
            </Expandable>
          </template>
        </section>
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

const conditionCount = (context) =>
  context.group.filters.length + (context.alternativeGroup?.filters.length || 0)
const otherConditionCount = computed(() =>
  props.readonlyGroups.reduce(
    (count, context) => count + conditionCount(context),
    0
  )
)
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
