import _ from 'lodash'

export class MissingDataProviderError extends Error {
  constructor(dataProviderName) {
    super()
    this.message = `The following data provider is missing: ${dataProviderName}`
    this.dataProviderName = dataProviderName
  }
}

export class UnresolvablePathError extends Error {
  constructor(dataProviderName, path) {
    super()
    this.message = `The path '${path}' can't be resolved in the data provider: ${dataProviderName}`
    this.dataProviderName = dataProviderName
    this.path = path
  }
}

export class RuntimeFormulaContext {
  /**
   * ⚠️ !! Warning !! ⚠️
   *
   * If you console log the context, it will trigger an SSR error. You will
   * notice that properties are being `get` which are not from the expected set
   * of known properties. For example, you will see `toJSON` or `stack` appearing
   * in the console logs. This is a known bug, but only affects development.
   */
  constructor(dataProviders, applicationContext) {
    this.dataProviders = dataProviders
    this.applicationContext = applicationContext
  }

  /**
   * Returns the value for the given path. The first part of the path is
   * the data provider type, then the remaining parts are given to the data provider.
   *
   * @param {String} path the dotted path of the data we want to get.
   * @returns the data related to the path.
   */
  get(path) {
    const [providerName, ...rest] = _.toPath(path)

    const dataProviderType = this.dataProviders[providerName]
    if (!dataProviderType) {
      throw new MissingDataProviderError()
    }

    try {
      return dataProviderType.getDataChunk(this.applicationContext, rest)
    } catch (e) {
      console.debug(`DATA PROVIDER DEBUG: ${e}`)
      throw new UnresolvablePathError(dataProviderType.type, rest.join('.'))
    }
  }
}

export default RuntimeFormulaContext
