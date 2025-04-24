const productionEnvs = ['production', 'prod']

export function warn(message, ...args) {
  if (isDev()) {
    console.warn(`[Vue Flow]: ${message}`, ...args)
  }
}

export function isDev() {
  // Utiliser process.env.NODE_ENV si disponible, sinon default à 'development'
  const currentEnv =
    typeof process !== 'undefined' && process.env && process.env.NODE_ENV
      ? process.env.NODE_ENV
      : 'development'

  return !productionEnvs.includes(currentEnv)
}
