<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import Decimal from 'decimal.js'
import { createCommunity } from '@/api/communities'
import { apiErrorMessage } from '@/api/client'
import UnitRow from '@/components/UnitRow.vue'

const router = useRouter()

const name = ref('')
const street = ref('')
const number = ref('')
const city = ref('')
const postalCode = ref('')
const province = ref('')
const cif = ref('')

let nextUnitKey = 0
function newUnit() {
  nextUnitKey += 1
  return { key: nextUnitKey, identifier: '', percentage: '' }
}
const units = ref([newUnit(), newUnit()])

function addUnit() {
  units.value.push(newUnit())
}
function removeUnit(index) {
  units.value.splice(index, 1)
}

// Parses a percentage string as an exact Decimal, or null if it isn't a
// valid positive number. Uses decimal.js (not native JS numbers) throughout
// this view because the backend checks participation coefficients for
// EXACT equality to 1, not a tolerance -- binary float rounding here could
// make a total that displays as "100.00%" fail server-side.
function parsePercentage(raw) {
  try {
    const value = new Decimal(raw)
    return value.gt(0) ? value : null
  } catch {
    return null
  }
}

const totalPercentage = computed(() => {
  return units.value.reduce((sum, unit) => {
    const value = parsePercentage(unit.percentage)
    return value ? sum.plus(value) : sum
  }, new Decimal(0))
})

const allPercentagesValid = computed(() =>
  units.value.every((unit) => parsePercentage(unit.percentage) !== null),
)
const allIdentifiersFilled = computed(() =>
  units.value.every((unit) => unit.identifier.trim().length > 0),
)
const totalIsExactly100 = computed(() => totalPercentage.value.eq(100))

const canSubmit = computed(
  () =>
    name.value.trim().length > 0 &&
    street.value.trim().length > 0 &&
    number.value.trim().length > 0 &&
    city.value.trim().length > 0 &&
    postalCode.value.trim().length > 0 &&
    province.value.trim().length > 0 &&
    cif.value.trim().length > 0 &&
    units.value.length > 0 &&
    allIdentifiersFilled.value &&
    allPercentagesValid.value &&
    totalIsExactly100.value,
)

const errorMessage = ref('')
const submitting = ref(false)

async function onSubmit() {
  errorMessage.value = ''
  submitting.value = true
  try {
    const payload = {
      name: name.value,
      street: street.value,
      number: number.value,
      city: city.value,
      postal_code: postalCode.value,
      province: province.value,
      cif: cif.value,
      units: units.value.map((unit) => ({
        identifier: unit.identifier,
        // Sent as a string, not a JS number, so the exact decimal digits
        // survive the trip to Pydantic's Decimal field untouched.
        participation_coefficient: parsePercentage(unit.percentage).dividedBy(100).toString(),
        owner_ids: [],
      })),
    }
    const community = await createCommunity(payload)
    router.push({ name: 'community-detail', params: { id: community.id } })
  } catch (error) {
    errorMessage.value = apiErrorMessage(error)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <v-row justify="center">
    <v-col cols="12" md="8">
      <v-card>
        <v-card-title>Registrar comunidad</v-card-title>
        <v-card-text>
          <v-alert v-if="errorMessage" type="error" density="compact" class="mb-4">
            {{ errorMessage }}
          </v-alert>

          <v-form @submit.prevent="onSubmit">
            <v-text-field v-model="name" label="Nombre de la comunidad" required />
            <v-row dense>
              <v-col cols="8"><v-text-field v-model="street" label="Calle" required /></v-col>
              <v-col cols="4"><v-text-field v-model="number" label="Número" required /></v-col>
            </v-row>
            <v-row dense>
              <v-col cols="6"><v-text-field v-model="city" label="Ciudad" required /></v-col>
              <v-col cols="3">
                <v-text-field v-model="postalCode" label="Código postal" required />
              </v-col>
              <v-col cols="3">
                <v-text-field v-model="province" label="Provincia" required />
              </v-col>
            </v-row>
            <v-text-field v-model="cif" label="CIF" required />

            <v-divider class="my-4" />

            <div class="d-flex align-center justify-space-between mb-2">
              <span class="text-subtitle-1">Unidades</span>
              <v-chip :color="totalIsExactly100 ? 'success' : 'warning'" variant="flat">
                Total: {{ totalPercentage.toString() }}%
              </v-chip>
            </div>

            <UnitRow
              v-for="(unit, index) in units"
              :key="unit.key"
              v-model="units[index]"
              :removable="units.length > 1"
              @remove="removeUnit(index)"
            />

            <v-btn variant="tonal" class="mb-4" @click="addUnit">Añadir unidad</v-btn>

            <v-alert
              v-if="!totalIsExactly100 && allPercentagesValid"
              type="warning"
              density="compact"
              class="mb-4"
            >
              Los coeficientes deben sumar exactamente 100%.
            </v-alert>

            <v-btn type="submit" color="primary" block :disabled="!canSubmit" :loading="submitting">
              Crear comunidad
            </v-btn>
          </v-form>
        </v-card-text>
      </v-card>
    </v-col>
  </v-row>
</template>
