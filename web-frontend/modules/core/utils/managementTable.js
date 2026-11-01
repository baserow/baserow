/** Keep identity and role controls stable; let other columns share spare space. */
export function getManagementTableLayout(columns, roleColumnKey) {
  const widths = {
    name: 'clamp(200px, 20cqw, 360px)',
    email: 'clamp(120px, 20cqw, 360px)',
    [roleColumnKey]: '270px',
    two_factor_auth: '64px',
    null: '64px',
  }

  return {
    fixedLayout: true,
    // Members need space for both identity columns; teams and agents need less.
    minTableWidth: columns.some(({ key }) => key === 'email')
      ? '1000px'
      : '700px',
    columnWidths: Object.fromEntries(
      columns.map(({ key }) => [key, widths[key] || 'auto'])
    ),
  }
}
