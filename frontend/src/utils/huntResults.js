import { assembleCorrelationResults } from './correlationResults'

/** Adapt authorized Hunt output without synthesizing an execution-complete event. */
export function huntCorrelationEvents(step) {
  const output = step.output
  const results = Array.isArray(output) ? output : output?.results || output?.data || []
  return [
    ...results.map((result) =>
      result?.type && result?.data ? result : { type: 'data', data: result },
    ),
    ...(output?.errors || []).map((error) => ({
      type: 'error',
      data: typeof error === 'string' ? { message: error } : error,
    })),
  ]
}

export function huntResultCount(step) {
  if (step.plugin_name === 'CorrelationScan') {
    return assembleCorrelationResults(huntCorrelationEvents(step)).filter(
      (event) => event.type === 'data' && Array.isArray(event.data?.matches),
    ).length
  }
  return step.output?.result_count ?? step.output?.results?.length ?? 0
}
