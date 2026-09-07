/** Extract callback credentials without accessing or changing browser state. */
export const getUserSourceCallbackToken = (query, provider, userSourceId) => {
  const value = query[`user_source_${provider}_token__${userSourceId}`]
  return typeof value === 'string' && value.length > 0 ? value : null
}

/** Return a clean callback URL and its single credential, if this is a callback. */
export const consumeUserSourceCallback = (url) => {
  const cleanUrl = new URL(url)
  const callbacks = [...cleanUrl.searchParams.keys()].filter((key) =>
    /^user_source_(saml|oidc)_token__\d+$/.test(key)
  )
  if (callbacks.length === 0) {
    return null
  }

  const tokens = callbacks.flatMap((key) => cleanUrl.searchParams.getAll(key))
  for (const key of callbacks) {
    cleanUrl.searchParams.delete(key)
  }

  // `next` is encoded by the login page and can contain another encoded URL.
  // Drop contaminated destinations rather than forwarding credentials again.
  for (const next of cleanUrl.searchParams.getAll('next')) {
    let decoded = next
    while (true) {
      if (
        /user_source_(saml|oidc)_token__/.test(decoded) ||
        tokens.some((token) => token && decoded.includes(token))
      ) {
        cleanUrl.searchParams.delete('next')
        break
      }
      // Credentials and parameter names are ASCII. Decode their percent escapes
      // without rejecting valid destinations containing a literal percent sign.
      const value = decoded.replace(/%([0-9a-f]{2})/gi, (_, hex) =>
        String.fromCharCode(parseInt(hex, 16))
      )
      if (value === decoded) {
        break
      }
      decoded = value
    }
  }

  return {
    token: tokens.length === 1 && tokens[0] ? tokens[0] : null,
    url: cleanUrl,
  }
}
