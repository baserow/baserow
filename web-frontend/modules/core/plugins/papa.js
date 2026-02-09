import Papa from 'papaparse'

export default defineNuxtPlugin((nuxtApp) => {
  Papa.parsePromise = function (file, config = {}) {
    return new Promise((resolve, reject) => {
      Papa.parse(file, { complete: resolve, error: reject, ...config })
    })
  }
  Papa.arrayToString = (array) => {
    return Papa.unparse([array])
  }
  Papa.stringToArray = (str) => {
    return Papa.parse(str).data[0]
  }

  return { provide: { papa: Papa } }
})
