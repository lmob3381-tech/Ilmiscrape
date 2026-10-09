self.addEventListener('install', (e) => {
    self.skipWaiting();
});

self.addEventListener('activate', (e) => {
    e.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (e) => {
    // Minimal fetch handler untuk memenuhi syarat PWA installability
    // Membiarkan browser menangani request secara normal
});
