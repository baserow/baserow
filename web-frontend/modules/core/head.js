export default {
  title: 'TCR Projects',
  titleTemplate: '%s | TCR Projects',
  meta: [
    { charset: 'utf-8' },
    {
      name: 'viewport',
      content:
        'width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no',
    },
    {
      name: 'format-detection',
      content: 'telephone=no, email=no, address=no, date=no',
    },
    {
      name: 'color-scheme',
      content: 'dark light',
    },
  ],
  script: [
    {
      innerHTML: `(function(){try{var t=localStorage.getItem('tcr-theme');if(t==='light'){document.documentElement.setAttribute('data-theme','light')}else if(t==='dark'){document.documentElement.setAttribute('data-theme','dark')}else if(window.matchMedia&&window.matchMedia('(prefers-color-scheme:light)').matches){/* system preference light - no attribute needed, CSS handles it */}else{document.documentElement.setAttribute('data-theme','dark')}}catch(e){}})()`,
      type: 'text/javascript',
    },
  ],
  link: [
    {
      rel: 'icon',
      type: 'image/png',
      href: '/img/favicon_16.png',
      sizes: '16x16',
      hid: true,
    },
    {
      rel: 'icon',
      type: 'image/png',
      href: '/img/favicon_32.png',
      sizes: '32x32',
      hid: true,
    },
    {
      rel: 'icon',
      type: 'image/png',
      href: '/img/favicon_48.png',
      sizes: '64x64',
      hid: true,
    },
    {
      rel: 'icon',
      type: 'image/png',
      href: '/img/favicon_192.png',
      sizes: '192x192',
      hid: true,
    },
  ],
}
