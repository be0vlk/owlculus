export const ROLE_OPTIONS = [
  {
    value: 'Analyst',
    title: 'Analyst',
    description: 'Read-only access to assigned cases',
    icon: 'mdi-chart-line',
    color: 'info',
  },
  {
    value: 'Investigator',
    title: 'Investigator',
    description: 'Read/write access, can run plugins',
    icon: 'mdi-account-search',
    color: 'primary',
  },
  {
    value: 'Admin',
    title: 'Administrator',
    description: 'Full system access and user management',
    icon: 'mdi-shield-check',
    color: 'error',
  },
]
