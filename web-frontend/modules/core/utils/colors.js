import styles from '@baserow/modules/core/assets/scss/colors.scss'

export const colors = Object.keys(styles)

/**
 * Returns a random color from the colors array.
 * @param {Array} excludeColors - Array of colors to exclude from the random
 * selection. If undefined or equal to the colors array, no colors will be
 * excluded. Returns a random color from the colors array.
 */
export const randomColor = (excludeColors = undefined) => {
  let palette = colors
  excludeColors = excludeColors || []
  if (excludeColors.length > 0 && excludeColors.length < colors.length) {
    palette = colors.filter((color) => !excludeColors.includes(color))
  }
  return palette[Math.floor(Math.random() * palette.length)]
}

export function convertHexToRgb(hex) {
  const hexWithoutHash = hex.replace(/^#/, '')

  const channels = []

  // Slice hex color string into two characters each.
  // For longhand hex color strings, two characters can be consumed at a time.
  const step = hexWithoutHash.length > 4 ? 2 : 1
  for (let i = 0; i < hexWithoutHash.length; i += step) {
    const channel = hexWithoutHash.slice(i, i + step)
    // Repeat the character once for shorthand hex color strings.
    channels.push(channel.repeat((step % 2) + 1))
  }

  if (channels.length === 3) {
    channels.push('ff')
  }

  const rgbChannels = channels.map((channel) => parseInt(channel, 16) / 255)

  return {
    r: rgbChannels[0],
    g: rgbChannels[1],
    b: rgbChannels[2],
    a: rgbChannels[3],
  }
}

export function convertHslToHsv(hsl) {
  const v = hsl.l + hsl.s * Math.min(hsl.l, 1 - hsl.l)
  const s = v === 0 ? 0 : 2 - (2 * hsl.l) / v

  return {
    h: hsl.h,
    s,
    v,
    a: hsl.a,
  }
}

export function convertHslToRgb(hsl) {
  const q = hsl.l < 0.5 ? hsl.l * (1 + hsl.s) : hsl.l + hsl.s - hsl.l * hsl.s
  const p = 2 * hsl.l - q

  return {
    r: hue2rgb(p, q, hsl.h + 1 / 3),
    g: hue2rgb(p, q, hsl.h),
    b: hue2rgb(p, q, hsl.h - 1 / 3),
    a: hsl.a,
  }
}

function hue2rgb(p, q, t) {
  if (t < 0) {
    t += 1
  } else if (t > 1) {
    t -= 1
  }

  if (t < 1 / 6) {
    return p + (q - p) * 6 * t
  } else if (t < 1 / 2) {
    return q
  } else if (t < 2 / 3) {
    return p + (q - p) * (2 / 3 - t) * 6
  } else {
    return p
  }
}

export function convertHsvToHsl(hsv) {
  const l = hsv.v - (hsv.v * hsv.s) / 2
  const lMin = Math.min(l, 1 - l)
  const s = lMin === 0 ? 0 : (hsv.v - l) / lMin

  return {
    h: hsv.h,
    s,
    l,
    a: hsv.a,
  }
}

function fn(n, hsv) {
  const k = (n + hsv.h * 6) % 6
  return hsv.v - hsv.v * hsv.s * Math.max(0, Math.min(k, 4 - k, 1))
}

export function convertHsvToRgb(hsv) {
  return {
    r: fn(5, hsv),
    g: fn(3, hsv),
    b: fn(1, hsv),
    a: hsv.a,
  }
}

export function convertHwbToHsv(hwb) {
  return {
    h: hwb.h,
    s: hwb.b === 1 ? 0 : 1 - hwb.w / (1 - hwb.b),
    v: 1 - hwb.b,
    a: hwb.a,
  }
}

export function convertRgbToHex(rgb) {
  const hexChannels = Object.values(rgb).map((channel) => {
    const int = channel * 255
    const hex = Math.round(int).toString(16)
    return hex.length === 1 ? '0' + hex : hex
  })

  return '#' + hexChannels.join('')
}

export function convertRgbToHsl(rgb) {
  const hwb = convertRgbToHwb(rgb)
  const min = hwb.w
  const max = 1 - hwb.b

  const l = (max + min) / 2

  let s
  if (max === 0 || min === 1) {
    s = 0
  } else {
    s = (max - l) / Math.min(l, 1 - l)
  }

  return {
    h: hwb.h,
    s,
    l,
    a: rgb.a,
  }
}

export function convertRgbToHwb(rgb) {
  const min = Math.min(rgb.r, rgb.g, rgb.b)
  const max = Math.max(rgb.r, rgb.g, rgb.b)

  let h
  if (max === min) {
    h = 0
  } else if (max === rgb.r) {
    h = (0 + (rgb.g - rgb.b) / (max - min)) / 6
  } else if (max === rgb.g) {
    h = (2 + (rgb.b - rgb.r) / (max - min)) / 6
  } else {
    h = (4 + (rgb.r - rgb.g) / (max - min)) / 6
  }

  if (h < 0) {
    h += 1
  }

  return {
    h,
    w: min,
    b: 1 - max,
    a: rgb.a,
  }
}

export function isValidHexColor(hexColor) {
  return /^#(?:(?:[A-F0-9]{2}){3,4}|[A-F0-9]{3,4})$/i.test(hexColor)
}

export function chainConvert(sourceColor, convertFunctions) {
  return convertFunctions.reduce(
    (color, convert) => convert(color),
    sourceColor
  )
}

export const conversionsMap = {
  hex: {
    hsl: (hex) => chainConvert(hex, [convertHexToRgb, convertRgbToHsl]),
    hsv: (hex) =>
      chainConvert(hex, [convertHexToRgb, convertRgbToHwb, convertHwbToHsv]),
    rgb: convertHexToRgb,
  },
  hsl: {
    hex: (hsl) => chainConvert(hsl, [convertHslToRgb, convertRgbToHex]),
    hsv: convertHslToHsv,
    rgb: convertHslToRgb,
  },
  hsv: {
    hex: (hsv) => chainConvert(hsv, [convertHsvToRgb, convertRgbToHex]),
    hsl: convertHsvToHsl,
    rgb: convertHsvToRgb,
  },
  rgb: {
    hex: convertRgbToHex,
    hsl: convertRgbToHsl,
    hsv: (rgb) => chainConvert(rgb, [convertRgbToHwb, convertHwbToHsv]),
  },
}

export function isColorVariable(value) {
  if (!value) {
    return false
  }
  return value.substring(0, 1) !== '#'
}

export function resolveColor(value, variables, recursively = true) {
  let varMap = variables
  if (Array.isArray(varMap)) {
    varMap = Object.fromEntries(variables.map((v) => [v.value, v]))
  }

  if (varMap[value]) {
    if (recursively) {
      return resolveColor(varMap[value].color, {
        ...varMap,
        [value]: undefined,
      })
    } else {
      return varMap[value].color
    }
  }

  // If the value is a color name, e.g, 'dark-green' use the color defined in
  // the SASS module.
  return styles[value] || value
}

/**
 * Return the color to mix depending on the luminance of the given color.
 * @param {string} hexColor The hex string of the color.
 * @returns `black` or `white` depending on the best match for the given color.
 */
export const colorRecommendation = (hexColor) => {
  // l is the luminance
  const hsl = conversionsMap.hex.hsl(hexColor)
  if (hsl.l > 0.8 || hsl.l < 0.2) {
    return 'gray'
  }
  if (hsl.l > 0.5) {
    return 'black'
  } else {
    return 'white'
  }
}

/**
 * Return the color lighten or darken depending on the initial color.
 * @param {string} hexColor The hex string of the color.
 * @returns The contrasted color.
 */
export const colorContrast = (hexColor, amount = 10) => {
  // l is the luminance
  const hsl = conversionsMap.hex.hsl(hexColor)
  if (hsl.l > 0.5) {
    hsl.l -= amount / 100
  } else {
    hsl.l += amount / 100
  }
  return conversionsMap.hsl.hex(hsl)
}
