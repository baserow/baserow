<template>
  <template v-if="groups.length">
    <div v-if="showLeadingOperator" class="dashboard-widget-filters__operator">
      <Badge size="small">{{ filterType }}</Badge>
    </div>
    <section class="dashboard-widget-filters__other">
      <div class="dashboard-widget-filters__other-header">
        <h3 class="dashboard-widget-filters__title">{{ title }}</h3>
        <Badge size="small">{{ conditionCount }}</Badge>
      </div>
      <template v-for="(context, index) in groups" :key="context.key">
        <div v-if="index" class="dashboard-widget-filters__operator">
          <Badge size="small">{{ filterType }}</Badge>
        </div>
        <Expandable
          :default-expanded="groups.length === 1"
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
              <span
                v-if="context.owner"
                class="dashboard-widget-filters__source-summary"
                >{{ conditionSummary(context) }}</span
              >
              <a
                v-if="context.owner && showEditLinks"
                class="dashboard-widget-filters__source-edit"
                role="button"
                tabindex="0"
                @click.stop="editOwner(context.owner)"
                @keydown.enter.stop.prevent="editOwner(context.owner)"
                >{{
                  $t('textFilterWidget.editInFilter', {
                    filter: context.title,
                  })
                }}</a
              >
              <HelpIcon
                v-else
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
              v-if="context.group?.filters?.length"
              small-label
              :label="
                context.owner ? $t('textFilterWidget.withValueTitle') : null
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
              :label="$t('textFilterWidget.whenEmptyTitle')"
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
</template>

<script setup>
import TargetFilterGroup from '@baserow/modules/dashboard/components/widget/TargetFilterGroup'
import { countFilterGroupConditions } from '@baserow/modules/dashboard/utils/widgetFilters'

const { $store, $i18n } = useNuxtApp()
const storePrefix = inject('storePrefix', ref(''))
const props = defineProps({
  groups: { type: Array, required: true },
  dashboard: { type: Object, required: true },
  fields: { type: Array, required: true },
  filterType: { type: String, default: 'AND' },
  title: { type: String, required: true },
  showLeadingOperator: { type: Boolean, default: true },
  /** Link each filter to its settings, where its conditions are edited. */
  showEditLinks: { type: Boolean, default: true },
})

/**
 * "4 conditions, any can match · 1 when empty": the conditions applied with a
 * value, and apart from them those applied when the filter is empty.
 */
const conditionSummary = ({ group, alternativeGroup }) => {
  const count = group?.filters?.length || 0
  const emptyCount = alternativeGroup?.filters?.length || 0
  const parts = []
  if (count || !emptyCount) {
    const conditions = $i18n.t(
      'textFilterWidget.conditionCount',
      { count },
      count
    )
    parts.push(
      count < 2
        ? conditions
        : $i18n.t('textFilterWidget.conditionSummary', {
            conditions,
            match:
              group?.filter_type === 'OR'
                ? $i18n.t('textFilterWidget.anyCanMatch')
                : $i18n.t('textFilterWidget.allMustMatch'),
          })
    )
  }
  if (emptyCount) {
    parts.push(
      $i18n.t(
        'textFilterWidget.whenEmptyCount',
        { count: emptyCount },
        emptyCount
      )
    )
  }
  return parts.join(' · ')
}
const editOwner = (owner) =>
  $store.dispatch(
    `${storePrefix.value ?? ''}dashboardApplication/selectWidget`,
    owner.id
  )

const conditionCount = computed(() => countFilterGroupConditions(props.groups))
</script>
