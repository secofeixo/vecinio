<script setup>
import { onMounted, ref } from 'vue'
import Decimal from 'decimal.js'
import { getCommunity } from '@/api/communities'
import { apiErrorMessage } from '@/api/client'

const props = defineProps({
  id: {
    type: String,
    required: true,
  },
})

const community = ref(null)
const errorMessage = ref('')
const loading = ref(true)

function asPercentage(coefficient) {
  return new Decimal(coefficient).times(100).toString()
}

onMounted(async () => {
  try {
    community.value = await getCommunity(props.id)
  } catch (error) {
    errorMessage.value = apiErrorMessage(error)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <v-row justify="center">
    <v-col cols="12" md="8">
      <v-progress-circular v-if="loading" indeterminate color="primary" />

      <v-alert v-else-if="errorMessage" type="error" density="compact">
        {{ errorMessage }}
      </v-alert>

      <v-card v-else-if="community">
        <v-card-title>{{ community.name }}</v-card-title>
        <v-card-subtitle>
          {{ community.address.street }} {{ community.address.number }},
          {{ community.address.city }} ({{ community.address.postal_code }},
          {{ community.address.province }}) — CIF {{ community.cif }}
        </v-card-subtitle>
        <v-card-text>
          <v-table>
            <thead>
              <tr>
                <th>Identificador</th>
                <th>Coeficiente</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="unit in community.units" :key="unit.id">
                <td>{{ unit.identifier }}</td>
                <td>{{ asPercentage(unit.participation_coefficient) }}%</td>
              </tr>
            </tbody>
          </v-table>
        </v-card-text>
        <v-card-actions>
          <v-btn variant="text" :to="{ name: 'community-create' }">
            Registrar otra comunidad
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-col>
  </v-row>
</template>
