<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { linkOwner } from '@/api/auth'
import { apiErrorMessage } from '@/api/client'

const router = useRouter()

const nif = ref('')
const canSubmit = computed(() => nif.value.trim().length > 0)

const errorMessage = ref('')
const submitting = ref(false)

async function onSubmit() {
  errorMessage.value = ''
  submitting.value = true
  try {
    await linkOwner({ nif: nif.value.trim() })
    router.push({ name: 'my-units' })
  } catch (error) {
    errorMessage.value = apiErrorMessage(error)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <v-row justify="center">
    <v-col cols="12" md="6">
      <v-card>
        <v-card-title>Vincular propietario</v-card-title>
        <v-card-text>
          <p class="mb-4">
            Indica tu NIF/NIE para vincular tu cuenta al propietario ya registrado con ese
            identificador. Si tu NIF/NIE no está registrado todavía, contacta con quien administra
            tu comunidad.
          </p>

          <v-alert v-if="errorMessage" type="error" density="compact" class="mb-4">
            {{ errorMessage }}
          </v-alert>

          <v-form @submit.prevent="onSubmit">
            <v-text-field v-model="nif" label="NIF/NIE" required />

            <v-btn type="submit" color="primary" block :disabled="!canSubmit" :loading="submitting">
              Vincular
            </v-btn>
          </v-form>
        </v-card-text>
      </v-card>
    </v-col>
  </v-row>
</template>
