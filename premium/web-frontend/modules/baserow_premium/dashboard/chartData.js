import { colorPalette, getBaseColors } from '@baserow/modules/core/utils/colors'

export function convertChartJsType(chartType) {
  if (!chartType) {
    return null
  }

  return chartType.toLowerCase()
}

function getIndividualSeriesConfig(seriesConfig, seriesId) {
  return seriesConfig.find((item) => item.series_id === seriesId) || {}
}

function getChartSeries(dataSource) {
  return (dataSource.aggregation_series || []).map((item) => {
    return {
      id: item.id,
      fieldName: `field_${item.field_id}`,
      aggregationType: item.aggregation_type,
    }
  })
}

function getAggregationTitle($registry, aggregationType) {
  return $registry.get('viewAggregation', aggregationType).getName()
}

function getServiceType({ dataSource, $registry }) {
  if (!dataSource.type || !$registry.exists('service', dataSource.type)) {
    return null
  }
  return $registry.get('service', dataSource.type)
}

function getResultPropertyName({ dataSource, propertyName }) {
  const property = dataSource.schema?.items?.properties?.[propertyName]
  if (property?.metadata?.aggregation) {
    return property.metadata.display_name || property?.title || propertyName
  }
  return property?.title || propertyName
}

function hasResultValue({ item, resultFieldName, fallbackFieldName = null }) {
  return (
    item[resultFieldName] !== undefined ||
    (fallbackFieldName !== null && item[fallbackFieldName] !== undefined)
  )
}

function getResultValue({ item, resultFieldName, fallbackFieldName = null }) {
  if (item[resultFieldName] !== undefined) {
    return item[resultFieldName]
  }
  if (fallbackFieldName !== null) {
    return item[fallbackFieldName]
  }
  return undefined
}

function getFieldTitle({ dataSource, $registry, series }) {
  const resultFieldName = `${series.fieldName}_${series.aggregationType}`
  const resultField = dataSource.schema.items.properties[resultFieldName]
  return (
    getServiceType({ dataSource, $registry })?.getSchemaPropertyDisplayName(
      dataSource,
      resultFieldName
    ) || resultField?.title
  )
}

function getLabel({ dataSource, $registry, series }) {
  const label = getAggregationTitle($registry, series.aggregationType)
  const fieldTitle = getFieldTitle({ dataSource, $registry, series })
  if (fieldTitle) {
    return `${fieldTitle} (${label})`
  }
  return label
}

function getGroupByValue({
  dataSource,
  $registry,
  $t,
  fieldName,
  resultFieldName,
  item,
}) {
  const serializedField = dataSource.context_data.fields[fieldName]
  const fieldType = serializedField.type
  const value = getResultValue({
    item,
    resultFieldName,
    fallbackFieldName: fieldName,
  })

  if (value === 'OTHER_VALUES') {
    return $t('chart.other')
  }

  if ($registry.exists('chartFieldFormatting', fieldType)) {
    const fieldFormatter = $registry.get('chartFieldFormatting', fieldType)
    return fieldFormatter.formatGroupByFieldValue(serializedField, value)
  }

  if (value === true) {
    return $t('chart.true')
  }

  if (value === false) {
    return $t('chart.false')
  }

  return value ?? ''
}

function getSeriesColors() {
  return getBaseColors().map((color) => {
    return {
      backgroundColor: color,
      borderColor: color,
      hoverBackgroundColor: color,
    }
  })
}

function getValuesColors() {
  return colorPalette.map((palette) => {
    return [
      palette[4].color,
      palette[6].color,
      palette[8].color,
      palette[0].color,
      palette[2].color,
      palette[9].color,
      palette[7].color,
      palette[5].color,
      palette[3].color,
      palette[1].color,
    ]
  })
}

function getChartColorsSeriesOrValues({ colorSeries, seriesIndex }) {
  if (colorSeries) {
    return getSeriesColors()[seriesIndex]
  } else {
    return {
      backgroundColor: getValuesColors()[seriesIndex],
    }
  }
}

function getChartDataGrouping({
  dataSource,
  results,
  seriesConfig,
  $registry,
  $t,
  colorSeries,
}) {
  const groupByFieldId = dataSource.aggregation_group_bys[0].field_id
  const primaryField = Object.values(dataSource.schema.items.properties).find(
    (item) => item.metadata?.primary === true
  )
  const labels = results.map((item) => {
    const groupByFieldName = `field_${groupByFieldId}`
    const groupByResultName = getResultPropertyName({
      dataSource,
      propertyName: groupByFieldName,
    })
    if (
      hasResultValue({
        item,
        resultFieldName: groupByResultName,
        fallbackFieldName: groupByFieldName,
      })
    ) {
      return getGroupByValue({
        dataSource,
        $registry,
        $t,
        fieldName: groupByFieldName,
        resultFieldName: groupByResultName,
        item,
      })
    }
    const primaryFieldName = `field_${primaryField.metadata.id}`
    const primaryResultName = getResultPropertyName({
      dataSource,
      propertyName: primaryFieldName,
    })
    return getGroupByValue({
      dataSource,
      $registry,
      $t,
      fieldName: primaryFieldName,
      resultFieldName: primaryResultName,
      item,
    })
  })
  const datasets = []
  for (const [index, series] of getChartSeries(dataSource).entries()) {
    const technicalResultFieldName = `${series.fieldName}_${series.aggregationType}`
    const resultFieldName = getResultPropertyName({
      dataSource,
      propertyName: technicalResultFieldName,
    })
    const seriesData = results.map((item) => {
      return getResultValue({
        item,
        resultFieldName,
        fallbackFieldName: technicalResultFieldName,
      })
    })
    const label = getLabel({ dataSource, $registry, series })
    const individualSeriesConfig = getIndividualSeriesConfig(
      seriesConfig,
      series.id
    )
    datasets.push({
      type:
        convertChartJsType(individualSeriesConfig.series_chart_type) || 'bar',
      data: seriesData,
      label,
      ...getChartColorsSeriesOrValues({ colorSeries, seriesIndex: index }),
    })
  }
  return {
    labels,
    datasets,
  }
}

function getChartDataNoGrouping({
  dataSource,
  results,
  seriesConfig,
  $registry,
  firstChartType,
}) {
  const result = results[0] || {}

  if (['pie', 'doughnut'].includes(firstChartType)) {
    const labels = []
    const data = []
    for (const series of getChartSeries(dataSource)) {
      const technicalResultFieldName = `${series.fieldName}_${series.aggregationType}`
      const resultFieldName = getResultPropertyName({
        dataSource,
        propertyName: technicalResultFieldName,
      })
      labels.push(getLabel({ dataSource, $registry, series }))
      data.push(
        getResultValue({
          item: result,
          resultFieldName,
          fallbackFieldName: technicalResultFieldName,
        })
      )
    }
    return {
      labels,
      datasets: [
        {
          type: firstChartType,
          data,
          backgroundColor: getValuesColors()[0],
        },
      ],
    }
  }

  const labels = ['']
  const datasets = []
  for (const [index, series] of getChartSeries(dataSource).entries()) {
    const technicalResultFieldName = `${series.fieldName}_${series.aggregationType}`
    const resultFieldName = getResultPropertyName({
      dataSource,
      propertyName: technicalResultFieldName,
    })
    const seriesData = [
      getResultValue({
        item: result,
        resultFieldName,
        fallbackFieldName: technicalResultFieldName,
      }),
    ]
    const label = getLabel({ dataSource, $registry, series })
    const individualSeriesConfig = getIndividualSeriesConfig(
      seriesConfig,
      series.id
    )
    datasets.push({
      type:
        convertChartJsType(individualSeriesConfig.series_chart_type) || 'bar',
      data: seriesData,
      label,
      ...getSeriesColors()[index],
    })
  }
  return {
    labels,
    datasets,
  }
}

export function getDashboardChartData({
  dataSource,
  dataSourceData,
  seriesConfig,
  $registry,
  $t,
}) {
  const results = dataSourceData?.results
  if (!results) {
    return {
      datasets: [],
    }
  }

  const firstSeriesConfig = getIndividualSeriesConfig(
    seriesConfig,
    getChartSeries(dataSource)[0]?.id
  )
  const firstChartType = convertChartJsType(firstSeriesConfig.series_chart_type)
  const colorSeries = !['pie', 'doughnut'].includes(firstChartType)

  if (!dataSource.aggregation_group_bys?.length) {
    return getChartDataNoGrouping({
      dataSource,
      results,
      seriesConfig,
      $registry,
      firstChartType,
    })
  }
  return getChartDataGrouping({
    dataSource,
    results,
    seriesConfig,
    $registry,
    $t,
    colorSeries,
  })
}
