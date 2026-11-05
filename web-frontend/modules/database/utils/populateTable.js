/** Add transient client state to an application child returned by the API. */
export function populateTable(table) {
  return {
    ...table,
    _: {
      disabled: false,
      selected: false,
    },
  }
}
