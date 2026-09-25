// List of values considered as true.
// Compatible with backend/src/baserow/contrib/database/fields/constants.py
export const trueValues = [
  't',
  'T',
  'y',
  'Y',
  'yes',
  'Yes',
  'YES',
  'true',
  'True',
  'TRUE',
  'o', // This one is not on the backend but was on the frontend
  'on',
  'On',
  'ON',
  '1',
  1,
  'checked',
  true,
]

// List of values considered as false.
// Compatible with backend/src/baserow/contrib/database/fields/constants.py
export const falseValues = [
  'f',
  'F',
  'n',
  'N',
  'no',
  'No',
  'NO',
  'false',
  'False',
  'FALSE',
  'off',
  'Off',
  'OFF',
  '0',
  0,
  0.0,
  'unchecked',
  false,
]

// Which sidebar the `app` layout renders, chosen by a page through
// `definePageMeta({ sidebarType })`. Defaults to the workspace one.
export const SIDEBAR_TYPES = {
  WORKSPACE: 'workspace',
  ALL_WORKSPACES: 'all-workspaces',
}
