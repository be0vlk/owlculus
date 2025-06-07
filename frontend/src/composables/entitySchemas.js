// Common field templates to reduce duplication
const commonFields = {
  address: [
    { id: 'street', label: 'Street', type: 'text', parentField: 'address', gridCols: 2 },
    { id: 'city', label: 'City', type: 'text', parentField: 'address' },
    { id: 'state', label: 'State', type: 'text', parentField: 'address' },
    { id: 'country', label: 'Country', type: 'text', parentField: 'address' },
    { id: 'postal_code', label: 'Postal Code', type: 'text', parentField: 'address' },
  ],
  socialMedia: [
    { id: 'bluesky', label: 'Bluesky', type: 'url' },
    { id: 'discord', label: 'Discord', type: 'text' },
    { id: 'facebook', label: 'Facebook', type: 'url' },
    { id: 'instagram', label: 'Instagram', type: 'url' },
    { id: 'linkedin', label: 'LinkedIn', type: 'url' },
    { id: 'reddit', label: 'Reddit', type: 'url' },
    { id: 'telegram', label: 'Telegram', type: 'url' },
    { id: 'tiktok', label: 'TikTok', type: 'url' },
    { id: 'twitch', label: 'Twitch', type: 'url' },
    { id: 'x', label: 'X', type: 'url' },
    { id: 'youtube', label: 'YouTube', type: 'url' },
    { id: 'other', label: 'Other', type: 'text' },
  ],
}

export const entitySchemas = {
  person: {
    basicInfo: {
      title: 'Basic Information',
      fields: [
        { id: 'first_name', label: 'First Name', type: 'text', gridCols: 2 },
        { id: 'last_name', label: 'Last Name', type: 'text', gridCols: 2 },
        { id: 'dob', label: 'Date of Birth', type: 'date' },
        { id: 'email', label: 'Email', type: 'email' },
        { id: 'phone', label: 'Phone', type: 'tel' },
        { id: 'employer', label: 'Employer', type: 'text' },
        { id: 'nationality', label: 'Nationality', type: 'text' },
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
        { id: 'children', label: 'Children', type: 'text' },
        { id: 'colleagues', label: 'Colleagues', type: 'text' },
        { id: 'father', label: 'Father', type: 'text' },
        { id: 'friends', label: 'Friends', type: 'text' },
        { id: 'mother', label: 'Mother', type: 'text' },
        { id: 'partner/spouse', label: 'Partner/Spouse', type: 'text' },
        { id: 'siblings', label: 'Siblings', type: 'text' },
        { id: 'other', label: 'Other', type: 'text' },
      ],
      parentField: 'associates',
    },
  },
  company: {
    basicInfo: {
      title: 'Basic Information',
      fields: [
        { id: 'name', label: 'Company Name', type: 'text', required: true },
        { id: 'website', label: 'Website', type: 'url', placeholder: 'example.com' },
        { id: 'phone', label: 'Phone', type: 'tel' },
        ...commonFields.address,
      ],
    },
    executives: {
      title: 'Executives',
      fields: [
        { id: 'ceo', label: 'CEO', type: 'text' },
        { id: 'cfo', label: 'CFO', type: 'text' },
        { id: 'cto', label: 'CTO', type: 'text' },
        { id: 'cmo', label: 'CMO', type: 'text' },
        { id: 'coo', label: 'COO', type: 'text' },
        { id: 'other', label: 'Other', type: 'text' },
      ],
      parentField: 'executives',
    },
    affiliates: {
      title: 'Affiliates',
      fields: [
        { id: 'affiliated_companies', label: 'Affiliated Companies', type: 'text' },
        { id: 'subsidiaries', label: 'Subsidiaries', type: 'text' },
        { id: 'parent_company', label: 'Parent Company', type: 'text' },
      ],
      parentField: 'affiliates',
    },
    socialMedia: {
      title: 'Social Media',
      fields: [
        { id: 'bluesky', label: 'Bluesky', type: 'url' },
        { id: 'discord', label: 'Discord', type: 'text' },
        { id: 'facebook', label: 'Facebook', type: 'url' },
        { id: 'instagram', label: 'Instagram', type: 'url' },
        { id: 'linkedin', label: 'LinkedIn', type: 'url' },
        { id: 'reddit', label: 'Reddit', type: 'url' },
        { id: 'telegram', label: 'Telegram', type: 'url' },
        { id: 'tiktok', label: 'TikTok', type: 'url' },
        { id: 'twitch', label: 'Twitch', type: 'url' },
        { id: 'x', label: 'X', type: 'url' },
        { id: 'youtube', label: 'YouTube', type: 'url' },
        { id: 'other', label: 'Other', type: 'text' },
      ],
      parentField: 'social_media',
    },
    domains: {
      title: 'Domains',
      fields: [{ id: 'domain', label: 'Domain', type: 'text', isArray: true }],
      parentField: 'domains',
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
        },
        {
          id: 'description',
          label: 'Description',
          type: 'textarea',
          placeholder: 'Add any notes or context about this domain',
        },
      ],
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
        },
        {
          id: 'description',
          label: 'Description',
          type: 'textarea',
          placeholder: 'Add any notes or context about this IP address',
        },
      ],
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
        },
      ],
    },
  },
}
