const IMAGE_WITH_URL_REGEX =
  /!\[([^[\]]*(?:\\.[^[\]]*)*)\]\[([^\]]+)\]\(([^)]+)\)/g

export function preprocessRichTextImages(content) {
  if (!content) return { content: content || '', nameMap: {} }
  const nameMap = {}
  const processed = content.replace(
    IMAGE_WITH_URL_REGEX,
    (match, alt, name, url) => {
      nameMap[url] = name
      return `![${alt}](${url})`
    }
  )
  return { content: processed, nameMap }
}

export function stripImageUrls(content) {
  if (!content) return content || ''
  return content.replace(
    IMAGE_WITH_URL_REGEX,
    (match, alt, name) => `![${alt}][${name}]`
  )
}

const IMAGE_REF_REGEX = /!\[([^[\]]*(?:\\.[^[\]]*)*)\]\[[^\]]+\]/g

export function stripUnresolvedImageRefs(content) {
  if (!content) return content || ''
  return content.replace(IMAGE_REF_REGEX, (match, alt) => {
    return alt ? `🖼 ${alt}` : '🖼'
  })
}

export function replaceImagesWithPlaceholder(content) {
  if (!content) return content || ''
  content = stripImageUrls(content)
  return content.replace(IMAGE_REF_REGEX, (match, alt) => {
    return alt ? `🖼 ${alt}` : '🖼'
  })
}
