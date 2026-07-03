/**
 * The sorted ancestor-id chain that identifies a node's "level". Two nodes are
 * at the same level when these chains are equal.
 */
const levelOf = (ancestorsOf, node) =>
  ancestorsOf(node)
    .map((ancestor) => ancestor.id)
    .sort((a, b) => a - b)

const sameLevel = (a, b) =>
  a.length === b.length && a.every((id, index) => id === b[index])

/**
 * Whether `destinationNode` is a valid "Go to node" destination for `gotoNode`.
 *
 * This mirrors the backend `validate_goto_destination`: the destination must be
 * a non-trigger node, at the same level as the Go to node, and run before it (a
 * backward jump), and it cannot be the Go to node itself. Keeping the rule in a
 * single helper means the connector overlay, the destination dropdown and the
 * post-move store cleanup all agree on what a valid jump is.
 *
 * The graph lookups are passed in as callbacks so this stays free of any Vuex /
 * registry coupling and is trivially testable:
 *
 * @param {Object} gotoNode The source Go to node.
 * @param {Object} destinationNode The candidate destination node.
 * @param {Function} ancestorsOf `(node) => node[]` — the node's container ancestors.
 * @param {Function} previousNodesOf `(node) => node[]` — the nodes that run before it.
 * @param {Function} isTrigger `(node) => boolean` — whether the node is a trigger.
 * @returns {boolean} True when the jump is valid.
 */
export function isValidGotoDestination({
  gotoNode,
  destinationNode,
  ancestorsOf,
  previousNodesOf,
  isTrigger,
}) {
  if (!destinationNode || destinationNode.id === gotoNode.id) {
    return false
  }
  if (isTrigger(destinationNode)) {
    return false
  }
  if (
    !sameLevel(
      levelOf(ancestorsOf, gotoNode),
      levelOf(ancestorsOf, destinationNode)
    )
  ) {
    return false
  }
  return previousNodesOf(gotoNode).some(
    (node) => node.id === destinationNode.id
  )
}
