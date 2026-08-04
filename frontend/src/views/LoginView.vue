<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { apiErrorMessage } from '@/api/client'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const email = ref('')
const password = ref('')
const errorMessage = ref('')
const submitting = ref(false)
const justRegistered = route.query.registered === '1'

async function onSubmit() {
  errorMessage.value = ''
  submitting.value = true
  try {
    await auth.login({ email: email.value, password: password.value })
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
    <v-col cols="12" sm="8" md="5">
      <v-card>
        <v-card-title>Iniciar sesión</v-card-title>
        <v-card-text>
          <v-alert v-if="justRegistered" type="success" density="compact" class="mb-4">
            Cuenta creada. Ahora puedes iniciar sesión.
          </v-alert>
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
              autocomplete="current-password"
              required
            />
            <v-btn type="submit" color="primary" block :loading="submitting">
              Entrar
            </v-btn>
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-btn variant="text" :to="{ name: 'register' }">Crear una cuenta</v-btn>
        </v-card-actions>
      </v-card>
    </v-col>
  </v-row>
</template>
