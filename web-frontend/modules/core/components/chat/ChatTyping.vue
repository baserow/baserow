<template>
  <div class="chat-typing" aria-hidden="true">
    <span v-for="dot in 3" :key="dot" class="chat-typing__dot" />
  </div>
</template>
