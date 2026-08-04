<script setup>
import { computed, onMounted, ref } from 'vue'
import Decimal from 'decimal.js'
import { getMyUnits } from '@/api/owners'
import { apiErrorMessage } from '@/api/client'
import { groupUnitsByCommunity } from '@/utils/groupUnitsByCommunity'

const units = ref(null)
const errorMessage = ref('')
const ownerNotLinked = ref(false)
const loading = ref(true)

const groups = computed(() => (units.value ? groupUnitsByCommunity(units.value) : []))

function asPercentage(coefficient) {
  return new Decimal(coefficient).times(100).toString()
}

onMounted(async () => {
  try {
    units.value = await getMyUnits()
  } catch (error) {
    if (error.response?.status === 404) {
      ownerNotLinked.value = true
    } else {
      errorMessage.value = apiErrorMessage(error)
    }
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

      <div v-else-if="ownerNotLinked">
        <v-alert type="info" density="compact" class="mb-4">
          Tu cuenta no tiene ningún propietario vinculado todavía.
        </v-alert>
        <!-- TODO: enable once an owner-linking/onboarding screen exists -->
        <v-btn disabled color="primary">Vincular propietario</v-btn>
      </div>

      <v-alert v-else-if="groups.length === 0" type="info" density="compact">
        Aún no tienes viviendas asociadas a tu cuenta.
      </v-alert>

      <template v-else>
        <v-card v-for="group in groups" :key="group.communityId" class="mb-4">
          <v-card-title>{{ group.communityName }}</v-card-title>
          <v-card-subtitle>
            {{ group.communityAddress.street }} {{ group.communityAddress.number }},
            {{ group.communityAddress.city }} ({{ group.communityAddress.postal_code }},
            {{ group.communityAddress.province }})
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
                <tr v-for="unit in group.units" :key="unit.id">
                  <td>{{ unit.identifier }}</td>
                  <td>{{ asPercentage(unit.participationCoefficient) }}%</td>
                </tr>
              </tbody>
            </v-table>
          </v-card-text>
        </v-card>
      </template>
    </v-col>
  </v-row>
</template>
