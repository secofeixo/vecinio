<script setup>
import { RouterView } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
</script>

<template>
  <v-app>
    <v-app-bar v-if="auth.isAuthenticated" title="Vecinio" density="comfortable">
      <v-btn variant="text" :to="{ name: 'my-units' }">Mis viviendas</v-btn>
      <v-btn variant="text" :to="{ name: 'community-create' }">Nueva comunidad</v-btn>
      <v-spacer />
      <v-btn variant="text" @click="auth.logout()">Cerrar sesión</v-btn>
    </v-app-bar>

    <v-main>
      <v-container>
        <RouterView />
      </v-container>
    </v-main>
  </v-app>
</template>
