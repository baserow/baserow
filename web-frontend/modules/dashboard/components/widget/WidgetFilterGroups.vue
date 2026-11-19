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
              v-if="context.group?.filters?.length"
              small-label
              :label="context.owner ? $t('textFilterWidget.withValue') : null"
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
</template>

<script setup>
import TargetFilterGroup from '@baserow/modules/dashboard/components/widget/TargetFilterGroup'
import { countFilterGroupConditions } from '@baserow/modules/dashboard/utils/widgetFilters'

const props = defineProps({
  groups: { type: Array, required: true },
  dashboard: { type: Object, required: true },
  fields: { type: Array, required: true },
  filterType: { type: String, default: 'AND' },
  title: { type: String, required: true },
  showLeadingOperator: { type: Boolean, default: true },
})

const conditionCount = computed(() => countFilterGroupConditions(props.groups))
</script>
