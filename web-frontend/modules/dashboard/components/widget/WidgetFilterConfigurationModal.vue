<template>
  <Modal ref="modal" wide @hidden="modalOpen = false">
    <div v-if="modalOpen" class="dashboard-widget-filters">
      <h2 class="box__title">
        {{ $t('textFilterWidget.configureFilters') }}
      </h2>
      <div class="dashboard-widget-filters__target">{{ target.title }}</div>
      <div class="dashboard-widget-filters__description">
        {{ $t('textFilterWidget.combinedFilterHelp') }}
      </div>
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
              @update="$emit('update', { ...link, alternative_group: $event })"
            />
          </div>
        </section>
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

defineProps({
  widget: { type: Object, required: true },
  dashboard: { type: Object, required: true },
  target: { type: Object, required: true },
  source: { type: Object, required: true },
  link: { type: Object, required: true },
  fields: { type: Array, required: true },
  readonlyGroups: { type: Array, required: true },
})
defineEmits(['update'])

const modal = ref(null)
const modalOpen = ref(false)
const emptyGroup = () => ({
  filters: [],
  filter_groups: [],
  filter_type: 'AND',
})
const show = () => {
  modalOpen.value = true
  modal.value.show()
}
const hide = () => modal.value.hide()

defineExpose({ show, hide })
</script>
