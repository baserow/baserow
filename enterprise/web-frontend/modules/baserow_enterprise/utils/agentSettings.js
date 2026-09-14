export const STYLE_TEMPERATURES = {
  precise: 0.1,
  balanced: 0.5,
  creative: 1.0,
}

/**
 * The style preset whose temperature is closest to the given one; a missing
 * temperature counts as the default precise 0.1.
 */
export function snapStyle(temperature) {
  const value =
    temperature === null || temperature === undefined || temperature === ''
      ? STYLE_TEMPERATURES.precise
      : parseFloat(temperature)
  let best = 'precise'
  let bestDistance = Infinity
  for (const [style, styleTemperature] of Object.entries(STYLE_TEMPERATURES)) {
    const distance = Math.abs(styleTemperature - value)
    if (distance < bestDistance) {
      best = style
      bestDistance = distance
    }
  }
  return best
}
