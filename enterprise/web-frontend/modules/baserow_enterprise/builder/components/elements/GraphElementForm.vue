<template>
  <form @submit.prevent @keydown.enter.prevent>
    <CustomStyleButton
      v-model="values.styles"
      style-key="graph"
      :config-block-types="['typography']"
      :theme="builder.theme"
      :extra-args="{
        onlyBody: true,
        noAlignment: true,
        noFontSelector: true,
        noFontWeight: true,
      }"
    />
    <FormGroup
      small-label
      required
      class="margin-bottom-2"
      :label="$t('graphElementForm.labels')"
      :helper-text="$t('graphElementForm.labelsHelper')"
    >
      <InjectedFormulaInput
        v-model="values.labels"
        :placeholder="$t('graphElementForm.labelsPlaceholder')"
      />
    </FormGroup>

    <FormSection
      class="margin-bottom-2"
      :title="$t('graphElementForm.seriesList')"
    >
      <template #title-slot>
        <ButtonText
          type="secondary"
          icon="iconoir-plus"
          size="small"
          @click="addSeries"
        >
          {{ $t('graphElementForm.addSeries') }}
        </ButtonText>
      </template>

      <div>
        <SidebarExpandable
          v-for="(series, index) in values.series"
          :key="seriesIds[index]"
          v-sortable="{
            id: seriesIds[index],
            update: orderSeries,
            handle: '[data-sortable-handle]',
          }"
          toggle-on-click
        >
          <template #title>
            <span>{{ getSeriesTitle(index) }}</span>
          </template>

          <template #default>
            <FormGroup
              small-label
              required
              class="margin-bottom-2"
              :label="$t('graphElementForm.seriesLabel')"
            >
              <InjectedFormulaInput
                :value="series.label"
                :placeholder="$t('graphElementForm.seriesLabelPlaceholder')"
                @input="updateSeries(index, 'label', $event)"
              />
            </FormGroup>

            <FormGroup
              small-label
              required
              class="margin-bottom-2"
              :label="$t('graphElementForm.seriesValues')"
              :helper-text="$t('graphElementForm.seriesValuesHelper')"
            >
              <InjectedFormulaInput
                :value="series.values"
                :placeholder="$t('graphElementForm.seriesValuesPlaceholder')"
                @input="updateSeries(index, 'values', $event)"
              />
            </FormGroup>

            <FormGroup
              small-label
              required
              class="margin-bottom-2"
              :label="$t('graphElementForm.chartType')"
            >
              <Dropdown
                :value="series.chart_type"
                :show-search="false"
                @input="updateSeries(index, 'chart_type', $event)"
              >
                <DropdownItem
                  :name="$t('graphElementForm.barChart')"
                  value="BAR"
                ></DropdownItem>
                <DropdownItem
                  :name="$t('graphElementForm.lineChart')"
                  value="LINE"
                ></DropdownItem>
              </Dropdown>
            </FormGroup>

            <FormGroup
              small-label
              required
              class="margin-bottom-2"
              :label="$t('graphElementForm.seriesColor')"
            >
              <ColorInput
                :value="series.color"
                :color-variables="colorVariables"
                @input="updateSeries(index, 'color', $event)"
              />
            </FormGroup>
          </template>

          <template #footer>
            <ButtonText icon="iconoir-bin" @click="removeSeries(index)">
              {{ $t('action.delete') }}
            </ButtonText>
          </template>
        </SidebarExpandable>
      </div>
    </FormSection>
  </form>
</template>

<script>
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import CustomStyleButton from '@baserow/modules/builder/components/elements/components/forms/style/CustomStyleButton'
import elementForm from '@baserow/modules/builder/mixins/elementForm'
import SidebarExpandable from '@baserow/modules/builder/components/SidebarExpandable.vue'
import { uuid } from '@baserow/modules/core/utils/string'

export default {
  name: 'GraphElementForm',
  components: { CustomStyleButton, InjectedFormulaInput, SidebarExpandable },
  mixins: [elementForm],
  data() {
    return {
      allowedValues: ['labels', 'series', 'styles'],
      values: {
        labels: {},
        series: [],
        styles: {},
      },
      seriesIds: [],
    }
  },
  mounted() {
    if (this.values.series.length === 0) {
      this.addSeries()
    } else {
      this.syncSeriesIds()
    }
  },
  methods: {
    syncSeriesIds() {
      while (this.seriesIds.length < this.values.series.length) {
        this.seriesIds.push(uuid())
      }
      if (this.seriesIds.length > this.values.series.length) {
        this.seriesIds = this.seriesIds.slice(0, this.values.series.length)
      }
    },
    addSeries() {
      this.values.series.push({
        label: '',
        values: '',
        color: 'primary',
        chart_type: 'BAR',
      })
      this.seriesIds.push(uuid())
    },
    removeSeries(index) {
      this.values.series.splice(index, 1)
      this.seriesIds.splice(index, 1)
    },
    updateSeries(index, key, value) {
      this.values.series.splice(index, 1, {
        ...this.values.series[index],
        [key]: value,
      })
    },
    getSeriesTitle(index) {
      return this.$t('graphElementForm.series', { number: index + 1 })
    },
    orderSeries(newOrder) {
      const seriesById = Object.fromEntries(
        this.values.series.map((series, index) => [
          this.seriesIds[index],
          series,
        ])
      )
      const orderedSeriesIds = newOrder.filter(
        (seriesId) => seriesById[seriesId]
      )
      this.values.series = orderedSeriesIds.map(
        (seriesId) => seriesById[seriesId]
      )
      this.seriesIds = orderedSeriesIds
    },
  },
}
</script>
