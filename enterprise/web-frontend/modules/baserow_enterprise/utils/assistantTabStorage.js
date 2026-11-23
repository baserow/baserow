import { uuid } from '@baserow/modules/core/utils/string'

const TAB_ID_KEY = 'baserow.assistant.tabId'
const CHAT_UUID_KEY = 'baserow.assistant.chatUuid'
const PANEL_OPEN_KEY = 'baserow.assistant.panelOpen'
const ONBOARDING_RUN_ID_KEY = 'baserow.assistant.onboardingRunId'

const inMemory = { [TAB_ID_KEY]: null, [ONBOARDING_RUN_ID_KEY]: null }

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

/**
 * A duplicated tab copies sessionStorage, so what must stay with one tab lives
 * in memory and is stored only once its page goes away: during a reload, and
 * for as long as the tab shows another site. A tab duplicated meanwhile gets
 * the same values.
 */
function leaveForNextPage() {
  for (const [key, value] of Object.entries(inMemory)) {
    write(key, value)
  }
}

function takeFromPreviousPage() {
  for (const key of Object.keys(inMemory)) {
    inMemory[key] = read(key) || inMemory[key]
    write(key, null)
  }
}

if (import.meta.client) {
  takeFromPreviousPage()
  window.addEventListener('pagehide', leaveForNextPage)
  window.addEventListener('pageshow', takeFromPreviousPage)
}

/**
 * @returns {string} This tab's id, kept across reloads, so Kuma's navigation
 *   follows only the tab that sent the message.
 */
export function getTabId() {
  inMemory[TAB_ID_KEY] ??= uuid()
  return inMemory[TAB_ID_KEY]
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
 *   whose first table opens once the run is done, also after a reload.
 */
export function getOnboardingRunId() {
  return inMemory[ONBOARDING_RUN_ID_KEY]
}

export function setOnboardingRunId(runId) {
  inMemory[ONBOARDING_RUN_ID_KEY] = runId
}
