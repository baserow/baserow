export function convertChartJsType(chartType) {
  if (!chartType) {
    return null
  }

  return chartType.toLowerCase()
}
