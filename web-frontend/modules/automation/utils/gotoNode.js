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
 * Whether jumping from `gotoNode` to `destinationNode` is a backward jump: the
 * destination runs before the Go to node, so it is one of its previous nodes.
 * A valid jump (see `isValidGotoDestination`) that is not backward is a forward
 * jump, which skips the nodes in between. The editor uses this to point a jump's
 * marker arrows the right way, and it is the primitive the same-path check below
 * is built from.
 *
 * @param {Object} gotoNode The source Go to node.
 * @param {Object} destinationNode The destination node.
 * @param {Function} previousNodesOf `(node) => node[]` — the nodes that run before it.
 * @returns {boolean} True when the destination runs before the Go to node.
 */
export function isBackwardGotoJump({
  gotoNode,
  destinationNode,
  previousNodesOf,
}) {
  return previousNodesOf(gotoNode).some(
    (node) => node.id === destinationNode.id
  )
}

/**
 * Whether `destinationNode` is a valid "Go to node" destination for `gotoNode`.
 *
 * This mirrors the backend `validate_goto_destination`: the destination must be
 * a non-trigger node, at the same level as the Go to node, and lie on the Go to
 * node's own path - either before it (a backward jump) or after it (a forward
 * jump that skips the nodes in between) - and it cannot be the Go to node
 * itself. Keeping the rule in a single helper means the connector overlay, the
 * destination dropdown and the post-move store cleanup all agree on what a valid
 * jump is.
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
  // On the same path when one node is in the other's previous nodes: the
  // destination runs before the Go to (a backward jump) or the Go to runs before
  // the destination (a forward jump, i.e. a backward jump seen from the
  // destination). A same-level node on a different branch is in neither and is
  // rejected.
  const isBackwardJump = isBackwardGotoJump({
    gotoNode,
    destinationNode,
    previousNodesOf,
  })
  const isForwardJump = isBackwardGotoJump({
    gotoNode: destinationNode,
    destinationNode: gotoNode,
    previousNodesOf,
  })
  return isBackwardJump || isForwardJump
}
