import {
  WORKSPACE_EXPORT_MANIFEST_CANDIDATES,
  WORKSPACE_EXPORT_MANIFEST_FILENAME,
} from '@baserow/modules/core/constants'

/**
 * Extracts the manifest from a ZIP using zip.js that does not load whole ZIP into memory.
 * BlobReader reads slices and the central directory so memory usage scales with the number
 *  of entries (the `entries` array) and the manifest size only.
 *
 * @param {Blob} zipFile
 * @returns {Promise<Object>} Parsed manifest JSON.
 * @throws {Error} If the archive is empty or the manifest is missing/invalid.
 */
export async function extractManifestFromZip(zipFile) {
  try {
    const zip = require('zipjs-umd')
    if (!zip) throw new Error('zip.js library not available on client')
    zip.configure({ useWebWorkers: false })
    const reader = new zip.ZipReader(new zip.BlobReader(zipFile))
    const entries = await reader.getEntries()
    if (!entries || entries.length === 0) {
      throw new Error('Empty ZIP archive')
    }
    const manifestEntry =
      entries.find((e) =>
        WORKSPACE_EXPORT_MANIFEST_CANDIDATES.includes(e.filename)
      ) ||
      entries.find(
        (e) =>
          e.filename.replace(/^\.\/+/, '') ===
          WORKSPACE_EXPORT_MANIFEST_FILENAME
      )
    if (!manifestEntry) {
      throw new Error('manifest.json not found in archive')
    }
    const text = await manifestEntry.getData(new zip.TextWriter())
    await reader.close()
    return JSON.parse(text)
  } catch (error) {
    throw new Error(error?.message || 'Failed to extract manifest')
  }
}

/**
 * Convert manifest data to application groups format for ApplicationSelector
 * @param {Object} manifest - The manifest data from the ZIP
 * @returns {Array} Application groups in the format expected by ApplicationSelector
 */
export function convertManifestToApplicationGroups(manifest) {
  if (!manifest || !manifest.applications) {
    return []
  }

  return Object.entries(manifest.applications)
    .map(([type, appData]) => ({
      type,
      applications: (appData?.items || []).map((item) => ({
        id: item.id,
        name: item.name,
        type: item.type || type,
      })),
    }))
    .filter((group) => group.applications.length > 0)
}
