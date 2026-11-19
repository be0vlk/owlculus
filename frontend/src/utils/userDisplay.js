export const isStrixy = (user) => user.system_identity === 'strixy'

export const userDisplayName = (user) => (isStrixy(user) ? 'Strixy (AI)' : user.username)
