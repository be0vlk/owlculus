import { reactive, computed, watch } from 'vue'

export function usePluginParamsAdvanced(props, emit, config = {}) {
  const { parameterDefaults = {}, customUpdateLogic = null } = config

  const pluginDescription = computed(() => {
    return props.parameters?.description || ''
  })

  const localParams = reactive({
    ...parameterDefaults,
    ...Object.fromEntries(
      Object.keys(parameterDefaults).map((key) => [
        key,
        props.modelValue[key] ?? parameterDefaults[key],
      ]),
    ),
  })

  const updateParams = () => {
    const updatedValue = {
      ...props.modelValue,
      ...localParams,
    }

    if (customUpdateLogic) {
      customUpdateLogic(updatedValue, localParams)
    }

    emit('update:modelValue', updatedValue)
  }

  watch(
    () => props.modelValue,
    (newValue) => {
      Object.assign(localParams, {
        ...Object.fromEntries(
          Object.keys(parameterDefaults).map((key) => [
            key,
            newValue[key] ?? parameterDefaults[key],
          ]),
        ),
      })
    },
    { deep: true },
  )

  return {
    pluginDescription,
    localParams,
    updateParams,
  }
}
