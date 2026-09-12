export const userDisplayName = (user) =>
  user.system_identity === 'strixy' ? 'Strixy (AI)' : user.username
