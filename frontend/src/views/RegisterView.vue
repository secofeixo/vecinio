<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { apiErrorMessage } from '@/api/client'

const router = useRouter()
const auth = useAuthStore()

const email = ref('')
const password = ref('')
const passwordConfirmation = ref('')
const errorMessage = ref('')
const submitting = ref(false)

// Advisory only, not authoritative: the backend does not itself validate
// email format or password strength (plain str fields), so this is purely
// to catch obvious mistakes before a round trip.
const passwordTooShort = computed(() => password.value.length > 0 && password.value.length < 8)
const passwordsMismatch = computed(
  () => passwordConfirmation.value.length > 0 && password.value !== passwordConfirmation.value,
)
const canSubmit = computed(
  () =>
    email.value.includes('@') &&
    password.value.length >= 8 &&
    password.value === passwordConfirmation.value,
)

async function onSubmit() {
  errorMessage.value = ''
  submitting.value = true
  try {
    await auth.register({ email: email.value, password: password.value })
    router.push({ name: 'login', query: { registered: '1' } })
  } catch (error) {
    errorMessage.value = apiErrorMessage(error)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <v-row justify="center">
    <v-col cols="12" sm="8" md="5">
      <v-card>
        <v-card-title>Crear cuenta</v-card-title>
        <v-card-text>
          <v-alert v-if="errorMessage" type="error" density="compact" class="mb-4">
            {{ errorMessage }}
          </v-alert>
          <v-form @submit.prevent="onSubmit">
            <v-text-field
              v-model="email"
              label="Email"
              type="email"
              autocomplete="username"
              required
            />
            <v-text-field
              v-model="password"
              label="Contraseña"
              type="password"
              autocomplete="new-password"
              :error-messages="passwordTooShort ? ['Mínimo 8 caracteres'] : []"
              required
            />
            <v-text-field
              v-model="passwordConfirmation"
              label="Repite la contraseña"
              type="password"
              autocomplete="new-password"
              :error-messages="passwordsMismatch ? ['Las contraseñas no coinciden'] : []"
              required
            />
            <v-btn
              type="submit"
              color="primary"
              block
              :disabled="!canSubmit"
              :loading="submitting"
            >
              Registrarme
            </v-btn>
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-btn variant="text" :to="{ name: 'login' }">Ya tengo cuenta</v-btn>
        </v-card-actions>
      </v-card>
    </v-col>
  </v-row>
</template>
