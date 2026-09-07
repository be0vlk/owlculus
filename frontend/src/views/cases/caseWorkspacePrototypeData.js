// THROWAWAY, fictional data shared by the baseline and the three design variants.
export const prototypeUsers = [
  {
    id: 1,
    username: 'Alex Morgan',
    email: 'alex@example.test',
    role: 'Investigator',
    is_lead: true,
  },
  {
    id: 2,
    username: 'Sam Rivera',
    email: 'sam@example.test',
    role: 'Investigator',
    is_lead: false,
  },
  { id: 3, username: 'Jamie Chen', email: 'jamie@example.test', role: 'Analyst', is_lead: false },
]
export const prototypeCases = [
  {
    id: 1,
    case_number: 'OWL-2026-041',
    title: 'Northstar — infrastructure investigation',
    status: 'Open',
    client_id: 1,
    created_at: '2026-09-01T09:00:00Z',
    users: prototypeUsers,
    notes:
      '<h2>Investigation notes</h2><p>Review the public infrastructure associated with Northstar Research. Separate observed links from working hypotheses.</p><h3>Working observations</h3><ul><li>The public website and mail gateway share a hosting provider.</li><li>Two archived pages mention the same company contact.</li><li>Registration dates alone do not establish common ownership.</li></ul><h3>Next steps</h3><p>Cross-check archived pages against the collected DNS records. Record each source and its collection date before drawing conclusions.</p>',
  },
  {
    id: 2,
    case_number: 'OWL-2026-042',
    title:
      'Meridian Holdings — cross-border corporate relationships and historical infrastructure review',
    status: 'Open',
    created_at: '2026-08-27T09:00:00Z',
    users: [
      ...prototypeUsers,
      ...Array.from({ length: 7 }, (_, i) => ({
        id: i + 4,
        username: `Researcher ${i + 4}`,
        is_lead: false,
      })),
    ],
    notes:
      '<h2>Meridian investigation</h2><p>A second case with a longer title, more assigned users, and no assigned client.</p>',
  },
]
export const prototypeEntities = [
  [
    'domain',
    {
      domain: 'northstar.example',
      description: 'Primary public website; first observed in the initial brief.',
      subdomains: ['mail', 'portal', 'cdn'],
    },
  ],
  [
    'company',
    {
      name: 'Northstar Research Ltd',
      website: 'https://northstar.example',
      description: 'Company named in the archived website footer.',
    },
  ],
  [
    'person',
    {
      first_name: 'Jordan',
      last_name: 'Ellis',
      email: 'j.ellis@example.test',
      description: 'Public contact listed on the research team page.',
    },
  ],
  [
    'ip_address',
    { ip_address: '203.0.113.24', description: 'Web hosting address from collected DNS records.' },
  ],
  [
    'domain',
    {
      domain: 'portal.northstar.example',
      description: 'Partner portal referenced in an archived help article.',
    },
  ],
  [
    'person',
    {
      first_name: 'Taylor',
      last_name: 'Brooks',
      email: 't.brooks@example.test',
      description: 'Named as a director in the public registry extract.',
    },
  ],
  [
    'company',
    {
      name: 'Harbor Digital Services',
      website: 'https://harbor.example',
      description: 'Service provider referenced by Northstar.',
    },
  ],
  [
    'domain',
    {
      domain: 'mail.northstar.example',
      description: 'Mail gateway from the initial DNS collection.',
    },
  ],
  [
    'ip_address',
    {
      ip_address: '198.51.100.18',
      description: 'Historical address from a retained infrastructure report.',
    },
  ],
  [
    'vehicle',
    {
      make: 'Ford',
      model: 'Transit',
      license_plate: 'DEMO 041',
      description: 'Vehicle visible in publicly available company photography.',
    },
  ],
  [
    'domain',
    {
      domain: 'research-archive.northstar.example',
      description: 'Longer archive hostname used to assess table readability.',
    },
  ],
  [
    'company',
    {
      name: 'Meridian Holdings',
      website: 'https://meridian.example',
      description: 'Potential related organization; relationship unconfirmed.',
    },
  ],
].map(([entity_type, data], i) => ({
  id: i + 1,
  entity_type,
  data,
  case_id: 1,
  created_at: `2026-09-0${6 - Math.floor(i / 3)}T10:30:00Z`,
}))

export const prototypeEvidence = [
  {
    id: 101,
    title: 'Corporate records',
    is_folder: true,
    children: [
      {
        id: 201,
        title: 'Northstar Research — company registry extract.pdf',
        is_folder: false,
        file_size: 284000,
        description: 'Public company registry, collected 6 Sep 2026',
      },
      {
        id: 202,
        title: 'Director appointments and historical addresses.pdf',
        is_folder: false,
        file_size: 176000,
        description: 'Supplementary filing, collected 6 Sep 2026',
      },
    ],
  },
  {
    id: 102,
    title: 'Infrastructure',
    is_folder: true,
    children: [
      {
        id: 203,
        title: 'northstar.example — DNS records.json',
        is_folder: false,
        file_size: 18000,
        description: 'Retained DNS lookup results',
      },
      {
        id: 204,
        title: 'Historical hosting observations.csv',
        is_folder: false,
        file_size: 42000,
        description: 'Working collection, 5 Sep 2026',
      },
    ],
  },
  {
    id: 103,
    title: 'Web captures',
    is_folder: true,
    children: [
      {
        id: 205,
        title: 'Research team — archived public website.png',
        is_folder: false,
        file_size: 940000,
        description: 'Archived capture, 4 Sep 2026',
      },
    ],
  },
].map((folder) => ({
  ...folder,
  case_id: 1,
  created_at: '2026-09-06T09:00:00Z',
  children: folder.children.map((file) => ({
    ...file,
    case_id: 1,
    parent_folder_id: folder.id,
    created_at: '2026-09-06T09:00:00Z',
  })),
}))

export const prototypeRuns = [
  {
    id: 501,
    plugin_name: 'DNS Lookup',
    parameters: { domain: 'northstar.example' },
    status: 'completed',
    created_at: '2026-09-06T14:32:00Z',
    dispatch_state: 'finished',
  },
  {
    id: 502,
    plugin_name: 'WHOIS',
    parameters: { domain: 'northstar.example' },
    status: 'completed',
    created_at: '2026-09-06T14:29:00Z',
    dispatch_state: 'finished',
  },
  {
    id: 503,
    plugin_name: 'Subdomain Enumeration',
    parameters: { domain: 'northstar.example' },
    status: 'failed',
    created_at: '2026-09-05T16:08:00Z',
    dispatch_state: 'finished',
    error: { message: 'Provider timed out. These are sample results.' },
  },
].map((run) => ({ ...run, case_id: 1, progress: 1, version: 1 }))

export const prototypeHuntExecutions = [
  {
    id: 501,
    case_id: 1,
    hunt_display_name: 'Domain infrastructure review',
    hunt_category: 'domain',
    initial_parameters: { domain: 'northstar.example' },
    status: 'completed',
    progress: 1,
    created_at: '2026-09-06T14:30:00Z',
    steps: [
      { name: 'DNS Lookup', status: 'completed', summary: 'Public DNS records collected.' },
      { name: 'WHOIS', status: 'completed', summary: 'Registration information retained.' },
    ],
  },
]
