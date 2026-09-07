// THROWAWAY: an isolated Vite server. Every /api request terminates here.
import { createServer } from 'vite'
import { fileURLToPath } from 'node:url'
import {
  prototypeCases,
  prototypeUsers,
  prototypeEntities,
  prototypeEvidence,
  prototypeRuns,
  prototypeHuntExecutions,
} from '../src/views/cases/caseWorkspacePrototypeData.js'

const root = fileURLToPath(new URL('../', import.meta.url))
const server = await createServer({
  root,
  configFile: `${root}vite.config.js`,
  define: {
    'import.meta.env.VITE_CASE_WORKSPACE_PROTOTYPE': 'true',
    'import.meta.env.VITE_API_BASE_URL': '""',
  },
  server: { host: '127.0.0.1', port: 5174, strictPort: true, open: '/case/1?variant=A' },
  plugins: [
    {
      name: 'throwaway-case-workspace-fixtures',
      transformIndexHtml() {
        return [
          {
            tag: 'script',
            injectTo: 'head-prepend',
            children:
              "localStorage.setItem('access_token', 'throwaway-prototype'); localStorage.setItem('token_type', 'bearer');",
          },
        ]
      },
      configureServer(vite) {
        vite.middlewares.use((req, res, next) => {
          const url = new URL(req.url, 'http://localhost')
          const path = url.pathname
          if (!path.startsWith('/api/')) return next()
          res.setHeader('Content-Type', 'application/json')
          if (req.method !== 'GET') {
            res.statusCode = 409
            res.end(
              JSON.stringify({
                detail:
                  'Throwaway preview: backend writes are disabled. Use the layout variants to try in-memory interactions.',
              }),
            )
            return
          }
          let body = []
          if (path === '/api/auth/setup-status') body = { setup_required: false }
          else if (path === '/api/users/me') body = prototypeUsers[0]
          else if (path === '/api/users/') body = prototypeUsers
          else if (path === '/api/cases/') body = prototypeCases
          else if (/^\/api\/cases\/\d+$/.test(path))
            body = prototypeCases.find((item) => item.id === Number(path.split('/')[3]))
          else if (/^\/api\/cases\/\d+\/users$/.test(path)) body = prototypeUsers
          else if (/^\/api\/cases\/\d+\/entities$/.test(path))
            body = path.includes('/1/')
              ? prototypeEntities
              : prototypeEntities.slice(0, 3).map((item) => ({ ...item, case_id: 2 }))
          else if (path.startsWith('/api/clients/')) body = { id: 1, name: 'Northstar review team' }
          else if (path.includes('/folder-tree')) body = prototypeEvidence
          else if (/^\/api\/hunts\/cases\/\d+\/executions$/.test(path))
            body = path.includes('/cases/1/') ? prototypeHuntExecutions : []
          else if (/^\/api\/hunts\/executions\/\d+$/.test(path))
            body = prototypeHuntExecutions.find((item) => item.id === Number(path.split('/').pop()))
          else if (path.startsWith('/api/plugins/executions/case/'))
            body = { items: path.endsWith('/1') ? prototypeRuns : [], next_cursor: null }
          else if (/^\/api\/plugins\/executions\/\d+$/.test(path))
            body = prototypeRuns.find((item) => item.id === Number(path.split('/').pop()))
          else if (path.endsWith('/results')) body = { items: [], next_cursor: null }
          res.end(JSON.stringify(body ?? {}))
        })
      },
    },
  ],
})
await server.listen()
server.printUrls()
console.log(
  'Throwaway case workspace: http://127.0.0.1:5174/case/1?variant=A — all API traffic uses fictional fixtures.',
)
