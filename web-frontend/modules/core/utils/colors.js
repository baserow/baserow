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

export const colorPalette = [
  [
    { color: '#D1E9FF' }, // blue 100
    { color: '#B2DDFF' }, // blue 200
    { color: '#84CAFF' }, // blue 300
    { color: '#53B1FD' }, // blue 400
    { color: '#2E90FA' }, // blue 500
    { color: '#1570EF' }, // blue 600
    { color: '#175CD3' }, // blue 700
    { color: '#1849A9' }, // blue 800
    { color: '#194185' }, // blue 900
    { color: '#102A56' }, // blue 1000
  ],
  [
    { color: '#FEF0C7' }, // orange 100
    { color: '#FEDF89' }, // orange 200
    { color: '#FEC84B' }, // orange 300
    { color: '#FDB022' }, // orange 400
    { color: '#F79009' }, // orange 500
    { color: '#DC6803' }, // orange 600
    { color: '#B54708' }, // orange 700
    { color: '#93370D' }, // orange 800
    { color: '#7A2E0E' }, // orange 900
    { color: '#4E1D09' }, // orange 1000
  ],
  [
    { color: '#F0FDF9' }, // teal 100
    { color: '#CCFBEF' }, // teal 200
    { color: '#99F6E0' }, // teal 300
    { color: '#5FE9D0' }, // teal 400
    { color: '#2ED3B7' }, // teal 500
    { color: '#15B79E' }, // teal 600
    { color: '#0E9384' }, // teal 700
    { color: '#107569' }, // teal 800
    { color: '#125D56' }, // teal 900
    { color: '#134E48' }, // teal 1000
  ],
  [
    { color: '#EFDCFB' }, // purple 100
    { color: '#DFB9F7' }, // purple 200
    { color: '#CF96F2' }, // purple 300
    { color: '#BF73EE' }, // purple 400
    { color: '#AF50EA' }, // purple 500
    { color: '#9D48D3' }, // purple 600
    { color: '#8C40BB' }, // purple 700
    { color: '#7B38A4' }, // purple 800
    { color: '#69308C' }, // purple 900
    { color: '#582875' }, // purple 1000
  ],
  [
    { color: '#D1E0FF' }, // dark blue 100
    { color: '#B2CCFF' }, // dark blue 200
    { color: '#84ADFF' }, // dark blue 300
    { color: '#528BFF' }, // dark blue 400
    { color: '#2970FF' }, // dark blue 500
    { color: '#155EEF' }, // dark blue 600
    { color: '#004EEB' }, // dark blue 700
    { color: '#0040C1' }, // dark blue 800
    { color: '#00359E' }, // dark blue 900
    { color: '#002266' }, // dark blue 1000
  ],
  [
    { color: '#FFF4DA' }, // yellow 100
    { color: '#FFE9B4' }, // yellow 200
    { color: '#FFDD8F' }, // yellow 300
    { color: '#FFD269' }, // yellow 400
    { color: '#FFC744' }, // yellow 500
    { color: '#E5B33D' }, // yellow 600
    { color: '#CC9F36' }, // yellow 700
    { color: '#B28B30' }, // yellow 800
    { color: '#997729' }, // yellow 900
    { color: '#806422' }, // yellow 1000
  ],
  [
    { color: '#FCE7F6' }, // pink 100
    { color: '#FCCEEE' }, // pink 200
    { color: '#FAA7E0' }, // pink 300
    { color: '#F670C7' }, // pink 400
    { color: '#EE46BC' }, // pink 500
    { color: '#DD2590' }, // pink 600
    { color: '#C11574' }, // pink 700
    { color: '#9E165F' }, // pink 800
    { color: '#851651' }, // pink 900
    { color: '#4E0D30' }, // pink 1000
  ],
  [
    { color: '#D0F6DC' }, // green 100
    { color: '#A0EEBA' }, // green 200
    { color: '#71E597' }, // green 300
    { color: '#41DD75' }, // green 400
    { color: '#12D452' }, // green 500
    { color: '#10BF4A' }, // green 600
    { color: '#0EAA42' }, // green 700
    { color: '#0D9439' }, // green 800
    { color: '#0B7F31' }, // green 900
    { color: '#096A29' }, // green 1000
  ],
  [
    { color: '#FEE4E2' }, // red 100
    { color: '#FECDCA' }, // red 200
    { color: '#FDA29B' }, // red 300
    { color: '#F97066' }, // red 400
    { color: '#F04438' }, // red 500
    { color: '#D92D20' }, // red 600
    { color: '#B42318' }, // red 700
    { color: '#912018' }, // red 800
    { color: '#7A271A' }, // red 900
    { color: '#55160C' }, // red 1000
  ],
  [
    { color: '#F3FEE7' }, // light green 100
    { color: '#E3FBCC' }, // light green 200
    { color: '#D0F8AB' }, // light green 300
    { color: '#A6EF67' }, // light green 400
    { color: '#85E13A' }, // light green 500
    { color: '#4CA30D' }, // light green 600
    { color: '#3B7C0F' }, // light green 700
    { color: '#326212' }, // light green 800
    { color: '#2B5314' }, // light green 900
    { color: '#15290A' }, // light green 1000
  ],
  [
    { color: '#FBE8FF' }, // fuchsia 100
    { color: '#F6D0FE' }, // fuchsia 200
    { color: '#EEAAFD' }, // fuchsia 300
    { color: '#E478FA' }, // fuchsia 400
    { color: '#D444F1' }, // fuchsia 500
    { color: '#BA24D5' }, // fuchsia 600
    { color: '#9F1AB1' }, // fuchsia 700
    { color: '#821890' }, // fuchsia 800
    { color: '#6F1877' }, // fuchsia 900
    { color: '#47104C' }, // fuchsia 1000
  ],
  [
    { color: '#D0F3FB' }, // cyan 100
    { color: '#B5EBFA' }, // cyan 200
    { color: '#7EDBF6' }, // cyan 300
    { color: '#47CBF3' }, // cyan 400
    { color: '#2BC3F1' }, // cyan 500
    { color: '#26B3DC' }, // cyan 600
    { color: '#21A3C6' }, // cyan 700
    { color: '#16829C' }, // cyan 800
    { color: '#117287' }, // cyan 900
    { color: '#0C6271' }, // cyan 1000
  ],
  [
    { color: '#FFE6D5' }, // dark orange 100
    { color: '#FFD6AE' }, // dark orange 200
    { color: '#FF9C66' }, // dark orange 300
    { color: '#FF692E' }, // dark orange 400
    { color: '#FF692E' }, // dark orange 500
    { color: '#FF4405' }, // dark orange 600
    { color: '#E62E05' }, // dark orange 700
    { color: '#BC1B06' }, // dark orange 800
    { color: '#97180C' }, // dark orange 900
    { color: '#771A0D' }, // dark orange 1000
  ],
  [
    { color: '#ECE9FE' }, // violet 100
    { color: '#DDD6FE' }, // violet 200
    { color: '#C3B5FD' }, // violet 300
    { color: '#A48AFB' }, // violet 400
    { color: '#875AF8' }, // violet 500
    { color: '#7839EE' }, // violet 600
    { color: '#6927DA' }, // violet 700
    { color: '#5720B7' }, // violet 800
    { color: '#491C96' }, // violet 900
    { color: '#2E125E' }, // violet 1000
  ],
  [
    { color: '#F5FBEE' }, // lime 100
    { color: '#E6F4D7' }, // lime 200
    { color: '#CEEAB0' }, // lime 300
    { color: '#ACDC79' }, // lime 400
    { color: '#86CB3C' }, // lime 500
    { color: '#669F2A' }, // lime 600
    { color: '#4F7A21' }, // lime 700
    { color: '#3F621A' }, // lime 800
    { color: '#335015' }, // lime 900
    { color: '#2B4212' }, // lime 1000
  ],
  [
    { color: '#DCDEFF' }, // indigo 100
    { color: '#B8BEFF' }, // indigo 200
    { color: '#959DFE' }, // indigo 300
    { color: '#717DFE' }, // indigo 400
    { color: '#4E5CFE' }, // indigo 500
    { color: '#4653E5' }, // indigo 600
    { color: '#3E4ACB' }, // indigo 700
    { color: '#3740B2' }, // indigo 800
    { color: '#2F3798' }, // indigo 900
    { color: '#272E7F' }, // indigo 1000
  ],
]

export const getBaseColors = () => {
  return colorPalette.map((palette) => palette[4].color)
}
