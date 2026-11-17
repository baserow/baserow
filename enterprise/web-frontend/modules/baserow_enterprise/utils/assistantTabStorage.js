import { uuid } from '@baserow/modules/core/utils/string'

const TAB_ID_KEY = 'baserow.assistant.tabId'
const CHAT_UUID_KEY = 'baserow.assistant.chatUuid'
const PANEL_OPEN_KEY = 'baserow.assistant.panelOpen'
const ONBOARDING_RUN_ID_KEY = 'baserow.assistant.onboardingRunId'

let tabId = null

function read(key) {
  try {
    return sessionStorage.getItem(key)
  } catch {
    return null
  }
}

function write(key, value) {
  try {
    if (value === null) {
      sessionStorage.removeItem(key)
    } else {
      sessionStorage.setItem(key, value)
    }
  } catch {}
}

function leaveTabIdForNextPage() {
  write(TAB_ID_KEY, tabId)
}

function takeTabIdFromPreviousPage() {
  tabId = read(TAB_ID_KEY) || tabId
  write(TAB_ID_KEY, null)
}

// Duplicated tabs copy sessionStorage, so the id is stored only between pages.
if (import.meta.client) {
  takeTabIdFromPreviousPage()
  window.addEventListener('pagehide', leaveTabIdForNextPage)
  window.addEventListener('pageshow', takeTabIdFromPreviousPage)
}

/**
 * @returns {string} This tab's id, kept across reloads, so Kuma's navigation
 *   follows only the tab that sent the message.
 */
export function getTabId() {
  tabId ??= uuid()
  return tabId
}

/**
 * @returns {string|null} The uuid of the chat the tab showed, reopened after
 *   a reload.
 */
export function getStoredChatUuid() {
  return read(CHAT_UUID_KEY)
}

export function storeChatUuid(chatUuid) {
  write(CHAT_UUID_KEY, chatUuid)
}

/**
 * @returns {boolean|null} Whether the panel was open in this tab, or null when
 *   the tab never said.
 */
export function getStoredPanelOpen() {
  const value = read(PANEL_OPEN_KEY)
  return value === null ? null : value === 'true'
}

export function storePanelOpen(open) {
  write(PANEL_OPEN_KEY, String(open))
}

/**
 * @returns {string|null} The run the onboarding handed over to this tab,
 *   whose first table opens once the run is done.
 */
export function getStoredOnboardingRunId() {
  return read(ONBOARDING_RUN_ID_KEY)
}

export function storeOnboardingRunId(runId) {
  write(ONBOARDING_RUN_ID_KEY, runId)
}
