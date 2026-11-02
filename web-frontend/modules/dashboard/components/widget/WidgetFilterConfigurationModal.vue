<template>
  <Modal ref="modal" wide @hidden="modalOpen = false">
    <div v-if="modalOpen" class="dashboard-widget-filters">
      <h2 class="box__title">
        {{ $t('textFilterWidget.filterTarget', { widget: target.title }) }}
      </h2>
      <div class="dashboard-widget-filters__description">
        {{ $t('textFilterWidget.configureHelp', { filter: widget.title }) }}
      </div>
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
        <template v-for="(context, index) in readonlyGroups" :key="context.key">
          <div v-if="index" class="dashboard-widget-filters__operator">
            <span>{{ source.filter_type }}</span>
          </div>
          <section
            class="dashboard-widget-filters__group dashboard-widget-filters__group--readonly"
          >
            <div class="dashboard-widget-filters__group-header">
              <h3 class="dashboard-widget-filters__group-title">
                {{ context.title }}
              </h3>
              <span class="dashboard-widget-filters__readonly"
                ><i class="iconoir-lock" />{{
                  $t('textFilterWidget.readOnly')
                }}</span
              >
            </div>
            <div class="dashboard-widget-filters__group-body">
              <TargetFilterGroup
                :group="context.group"
                :fields="fields"
                :dashboard="dashboard"
                :owner="context.owner"
                read-only
              />
            </div>
          </section>
        </template>
        <div
          v-if="readonlyGroups.length"
          class="dashboard-widget-filters__operator"
        >
          <span>
            {{ source.filter_type }}
          </span>
        </div>
        <section class="dashboard-widget-filters__group">
          <div class="dashboard-widget-filters__group-header">
            <h3 class="dashboard-widget-filters__group-title">
              {{ widget.title }}
            </h3>
          </div>
          <div class="dashboard-widget-filters__group-body">
            <TargetFilterGroup
              :key="target.id"
              :group="link.group"
              :fields="fields"
              :dashboard="dashboard"
              :owner="widget"
              @update="$emit('update', { ...link, group: $event })"
            />
          </div>
        </section>
        <FormGroup
          small-label
          :label="$t('textFilterWidget.emptyBehavior')"
          :helper-text="$t('textFilterWidget.emptyBehaviorHelp')"
          class="margin-top-2"
          required
        >
          <Dropdown
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
        </FormGroup>
        <template v-if="link.empty_behavior === 'apply_alternative'">
          <div class="dashboard-widget-filters__operator">
            <span>{{
              $t('textFilterWidget.alternativeSeparator', {
                operator: source.filter_type,
              })
            }}</span>
          </div>
          <section
            class="dashboard-widget-filters__group dashboard-widget-filters__group--alternative"
          >
            <div class="dashboard-widget-filters__group-header">
              <h3 class="dashboard-widget-filters__group-title">
                {{ $t('textFilterWidget.alternativeGroup') }}
              </h3>
            </div>
            <div class="dashboard-widget-filters__group-body">
              <TargetFilterGroup
                :key="`${target.id}-alternative`"
                :group="link.alternative_group || emptyGroup()"
                :fields="fields"
                :dashboard="dashboard"
                :owner="widget"
                @update="
                  $emit('update', { ...link, alternative_group: $event })
                "
              />
            </div>
          </section>
        </template>
      </template>
      <div class="actions actions--right dashboard-widget-filters__footer">
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
  modalOpen.value = true
  modal.value.show()
}
const hide = () => modal.value.hide()

defineExpose({ show, hide })
</script>
