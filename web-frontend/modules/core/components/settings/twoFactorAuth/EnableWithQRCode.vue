<template>
  <div class="enable-with-qr-code">
    <div class="enable-with-qr-code__step">
      <div class="enable-with-qr-code__number">1</div>
      <div>
        <div class="enable-with-qr-code__step-heading">Scan QR code</div>
        <div class="enable-with-qr-code__step-description">
          Scan the code with an app like Google Authenticator, Authy or
          Microsoft Authenticator, or click here to copy the code.
        </div>
      </div>
    </div>
    <div class="enable-with-qr-code__step">
      <div class="enable-with-qr-code__number">2</div>
      <div>
        <div class="enable-with-qr-code__step-heading">
          Enter the code shown
        </div>
        <div class="enable-with-qr-code__step-description">
          Enter a 6-digit code shown by the app to confirm that you have set it
          up correctly.
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'EnableWithQRCode',
}
</script>
