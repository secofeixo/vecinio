<script setup>
defineProps({
  modelValue: {
    type: Object,
    required: true,
  },
  removable: {
    type: Boolean,
    default: true,
  },
})

defineEmits(['update:modelValue', 'remove'])
</script>

<template>
  <v-row align="center" dense>
    <v-col cols="12" sm="5">
      <v-text-field
        :model-value="modelValue.identifier"
        label="Identificador (p. ej. 4º-2ª)"
        density="comfortable"
        required
        @update:model-value="$emit('update:modelValue', { ...modelValue, identifier: $event })"
      />
    </v-col>
    <v-col cols="8" sm="5">
      <v-text-field
        :model-value="modelValue.percentage"
        label="Coeficiente (%)"
        density="comfortable"
        suffix="%"
        required
        @update:model-value="$emit('update:modelValue', { ...modelValue, percentage: $event })"
      />
    </v-col>
    <v-col cols="4" sm="2" class="text-right">
      <v-btn
        v-if="removable"
        icon="mdi-close"
        variant="text"
        density="comfortable"
        @click="$emit('remove')"
      />
    </v-col>
  </v-row>
</template>
