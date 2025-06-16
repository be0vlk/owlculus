// Common field templates to reduce duplication
const commonFields = {
  address: [
    {
      id: 'street',
      label: 'Street',
      type: 'text',
      parentField: 'address',
      gridCols: 2,
      hasSource: true,
    },
    { id: 'city', label: 'City', type: 'text', parentField: 'address', hasSource: true },
    { id: 'state', label: 'State', type: 'text', parentField: 'address', hasSource: true },
    { id: 'country', label: 'Country', type: 'text', parentField: 'address', hasSource: true },
    {
      id: 'postal_code',
      label: 'Postal Code',
      type: 'text',
      parentField: 'address',
      hasSource: true,
    },
  ],
  socialMedia: [
    { id: 'bluesky', label: 'Bluesky', type: 'url', hasSource: true },
    { id: 'discord', label: 'Discord', type: 'text', hasSource: true },
    { id: 'facebook', label: 'Facebook', type: 'url', hasSource: true },
    { id: 'instagram', label: 'Instagram', type: 'url', hasSource: true },
    { id: 'linkedin', label: 'LinkedIn', type: 'url', hasSource: true },
    { id: 'reddit', label: 'Reddit', type: 'url', hasSource: true },
    { id: 'telegram', label: 'Telegram', type: 'url', hasSource: true },
    { id: 'tiktok', label: 'TikTok', type: 'url', hasSource: true },
    { id: 'twitch', label: 'Twitch', type: 'url', hasSource: true },
    { id: 'x', label: 'X', type: 'url', hasSource: true },
    { id: 'youtube', label: 'YouTube', type: 'url', hasSource: true },
    { id: 'other', label: 'Other', type: 'text', hasSource: true },
  ],
}

export const entitySchemas = {
  person: {
    basicInfo: {
      title: 'Basic Information',
      fields: [
        { id: 'first_name', label: 'First Name', type: 'text', gridCols: 2, hasSource: true },
        { id: 'last_name', label: 'Last Name', type: 'text', gridCols: 2, hasSource: true },
        { id: 'dob', label: 'Date of Birth', type: 'date', hasSource: true },
        { id: 'email', label: 'Email', type: 'email', hasSource: true },
        { id: 'phone', label: 'Phone', type: 'tel', hasSource: true },
        { id: 'employer', label: 'Employer', type: 'text', hasSource: true },
        { id: 'nationality', label: 'Nationality', type: 'text', hasSource: true },
        ...commonFields.address,
      ],
    },
    socialMedia: {
      title: 'Social Media',
      fields: commonFields.socialMedia,
      parentField: 'social_media',
    },
    associates: {
      title: 'Associates',
      fields: [
        { id: 'children', label: 'Children', type: 'text', hasSource: true },
        { id: 'colleagues', label: 'Colleagues', type: 'text', hasSource: true },
        { id: 'father', label: 'Father', type: 'text', hasSource: true },
        { id: 'friends', label: 'Friends', type: 'text', hasSource: true },
        { id: 'mother', label: 'Mother', type: 'text', hasSource: true },
        { id: 'partner/spouse', label: 'Partner/Spouse', type: 'text', hasSource: true },
        { id: 'siblings', label: 'Siblings', type: 'text', hasSource: true },
        { id: 'other', label: 'Other', type: 'text', hasSource: true },
      ],
      parentField: 'associates',
    },
    notes: {
      title: 'Notes',
      fields: [],
      isNoteEditor: true,
    },
  },
  company: {
    basicInfo: {
      title: 'Basic Information',
      fields: [
        { id: 'name', label: 'Company Name', type: 'text', required: true, hasSource: true },
        {
          id: 'website',
          label: 'Website',
          type: 'url',
          placeholder: 'example.com',
          hasSource: true,
        },
        { id: 'phone', label: 'Phone', type: 'tel', hasSource: true },
        ...commonFields.address,
      ],
    },
    executives: {
      title: 'Executives',
      fields: [
        { id: 'ceo', label: 'CEO', type: 'text', hasSource: true },
        { id: 'cfo', label: 'CFO', type: 'text', hasSource: true },
        { id: 'cto', label: 'CTO', type: 'text', hasSource: true },
        { id: 'cmo', label: 'CMO', type: 'text', hasSource: true },
        { id: 'coo', label: 'COO', type: 'text', hasSource: true },
        { id: 'other', label: 'Other', type: 'text', hasSource: true },
      ],
      parentField: 'executives',
    },
    affiliates: {
      title: 'Affiliates',
      fields: [
        {
          id: 'affiliated_companies',
          label: 'Affiliated Companies',
          type: 'text',
          hasSource: true,
        },
        { id: 'subsidiaries', label: 'Subsidiaries', type: 'text', hasSource: true },
        { id: 'parent_company', label: 'Parent Company', type: 'text', hasSource: true },
      ],
      parentField: 'affiliates',
    },
    socialMedia: {
      title: 'Social Media',
      fields: commonFields.socialMedia,
      parentField: 'social_media',
    },
    notes: {
      title: 'Notes',
      fields: [],
      isNoteEditor: true,
    },
  },
  domain: {
    basicInfo: {
      title: 'Domain Information',
      fields: [
        {
          id: 'domain',
          label: 'Domain Name',
          type: 'text',
          required: true,
          placeholder: 'example.com',
          hasSource: true,
        },
        {
          id: 'description',
          label: 'Description',
          type: 'textarea',
          placeholder: 'Add any notes or context about this domain',
          hasSource: true,
        },
      ],
    },
    subdomains: {
      title: 'Subdomains',
      fields: [
        {
          id: 'subdomains',
          label: 'Subdomains',
          type: 'array',
          isArray: true,
          arrayFields: ['subdomain', 'ip', 'resolved', 'source'],
        },
      ],
    },
    notes: {
      title: 'Notes',
      fields: [],
      isNoteEditor: true,
    },
  },
  ip_address: {
    basicInfo: {
      title: 'IP Address Information',
      fields: [
        {
          id: 'ip_address',
          label: 'IP Address',
          type: 'text',
          required: true,
          placeholder: '192.168.1.1',
          hasSource: true,
        },
        {
          id: 'description',
          label: 'Description',
          type: 'textarea',
          placeholder: 'Add any notes or context about this IP address',
          hasSource: true,
        },
      ],
    },
    notes: {
      title: 'Notes',
      fields: [],
      isNoteEditor: true,
    },
  },
  network_assets: {
    basicInfo: {
      title: 'Network Assets',
      fields: [
        {
          id: 'subdomains',
          label: 'Subdomains',
          type: 'text',
          isArray: true,
          placeholder: 'Enter subdomain and press Enter',
          hasSource: true,
        },
      ],
    },
    notes: {
      title: 'Notes',
      fields: [],
      isNoteEditor: true,
    },
  },
}
