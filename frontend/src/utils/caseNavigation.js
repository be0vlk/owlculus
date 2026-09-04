export function routeCaseId(route) {
  return route?.meta.caseScoped ? (route.params.caseId ?? route.params.id) : undefined
}

export function caseLocation(id, route, { overview = false } = {}) {
  if (!id) return { path: '/cases' }
  if (!overview && routeCaseId(route) && route.meta.caseSwitchable) {
    const query = { ...route.query }
    // Entity links name records owned by the old case, unlike workspace tabs.
    if (String(routeCaseId(route)) !== String(id)) delete query.entity
    const param = route.params.caseId === undefined ? 'id' : 'caseId'
    return { name: route.name, params: { ...route.params, [param]: id }, query, hash: route.hash }
  }
  return { name: 'CaseDetails', params: { id } }
}
