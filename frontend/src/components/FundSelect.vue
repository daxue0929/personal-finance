<template>
  <el-select
    :model-value="modelValue"
    :placeholder="placeholder"
    :disabled="disabled"
    :clearable="clearable"
    :loading="loading"
    filterable
    remote
    reserve-keyword
    :remote-method="handleRemote"
    @visible-change="onVisible"
    @change="onChange"
    :style="{ width }"
  >
    <el-option
      v-for="o in mergedOptions"
      :key="o.value"
      :label="o.label"
      :value="o.value"
    />
  </el-select>
</template>

<script setup>
import { computed, watch } from 'vue'
import { useFundSearch } from './useFundSearch'

// 基金代码下拉搜索选择公共组件：下拉可选 + 动态模糊搜索（代码/名称）+ 聚焦预载前 N 条。
// 交互细节（filterable/remote/reserve-keyword/防抖/默认20条）在组件内固化，不对外暴露，保证全站一致。
// 用法：<FundSelect v-model="form.fund_code" :disabled="isEdit" @select="onFundSelected" />
const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '输入代码或名称搜索' },
  width: { type: String, default: '100%' },
  disabled: { type: Boolean, default: false },
  clearable: { type: Boolean, default: true },
  pageSize: { type: Number, default: 20 }
})
const emit = defineEmits(['update:modelValue', 'select'])

const {
  options, loading, initialOption,
  search, loadDefault, resolveInitial, findInOptions, clear, pin
} = useFundSearch({ pageSize: props.pageSize })

// 合并初始回显项与搜索结果，按 value 去重，避免选中项不在前 20 条时 label 丢失
const mergedOptions = computed(() => {
  const list = [...options.value]
  if (initialOption.value && !list.some(o => o.value === initialOption.value.value)) {
    list.unshift(initialOption.value)
  }
  return list
})

// el-select remote-method 直接转发，search 内部已防抖 + 空 query 分流到 loadDefault
const handleRemote = (q) => search(q)

// 聚焦展开且尚无选项时预载前 N 条
const onVisible = (v) => {
  if (v && !options.value.length) loadDefault()
}

// 选中/清空：同步 v-model，并抛出完整 fund 对象（供联动回填 fund_name/净值）；清空抛 null
const onChange = (code) => {
  const v = code || ''
  emit('update:modelValue', v)
  if (v) pin(v)                       // 钉住选中项，防止后续搜索替换 options 时 label 丢失
  emit('select', v ? findInOptions(v) : null)
}

// modelValue 变化：空值清除残留（弹窗重置避免脏选项）；非空且不在选项中则回显 label
watch(() => props.modelValue, (code) => {
  if (!code) { clear(); return }
  if (!findInOptions(code)) resolveInitial(code)
}, { immediate: true })
</script>

<style scoped>
</style>
