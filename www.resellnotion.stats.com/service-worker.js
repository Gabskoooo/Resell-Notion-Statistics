const CACHE_NAME = 'my-pwa-cache-v3'; // CHANGÉ à v3 pour forcer la mise à jour
const urlsToCache = [
    '/', // La racine de votre application
    '/dashboard', // Votre page de tableau de bord (start_url du manifeste)
    '/login', // Votre page de connexion si elle doit être accessible hors ligne
    '/offline.html', // NOUVEAU : Page de secours hors ligne
    '/static/style.css',
    '/static/fonts/SpecialGothicExpandedOne-Regular.ttf', // VIRGULE AJOUTÉE
    '/static/logo.png',
    '/static/fond.png',
    '/static/placeholder.png',
    '/static/sku_not_found.png', // VIRGULE AJOUTÉE
    '/static/success_checkmark.png',
    '/static/template_wtb_wts.png'
    // Ajoutez ici TOUTES les ressources statiques (images, JS, CSS, fonts) essentielles
    // pour que votre application fonctionne hors ligne.
    // Par exemple, les fichiers Bootstrap JS et CSS si vous les auto-hébergez.
    // Si vous utilisez Bootstrap depuis un CDN, le Service Worker ne peut pas les cacher.
];

// Événement 'install' : le Service Worker est enregistré pour la première fois
self.addEventListener('install', event => {
    console.log('[Service Worker] Installation...');
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('[Service Worker] Cache ouvert, ajout des URLs');
                return cache.addAll(urlsToCache).then(() => {
                    console.log('[Service Worker] Toutes les URLs essentielles ont été mises en cache.');
                }).catch(error => {
                    console.error('[Service Worker] Échec de cache.addAll (une ou plusieurs ressources n\'ont pas pu être mises en cache) :', error);
                    // Regardez ici si des ressources donnent une erreur 404 (non trouvée)
                });
            })
    );
});

// Événement 'fetch' : intercepte les requêtes réseau
self.addEventListener('fetch', event => {
    event.respondWith(
        caches.match(event.request)
            .then(response => {
                // Si la ressource est dans le cache, la retourner
                if (response) {
                    console.log(`[Service Worker] Servie depuis le cache : ${event.request.url}`);
                    return response;
                }

                // Sinon, la récupérer depuis le réseau
                console.log(`[Service Worker] Tente de récupérer depuis le réseau : ${event.request.url}`);
                return fetch(event.request).catch(() => {
                    // Si la requête réseau échoue (ex: hors ligne)
                    // et que c'est une requête de navigation (pour une page HTML),
                    // servir la page de secours hors ligne.
                    if (event.request.mode === 'navigate') {
                        console.log('[Service Worker] Navigation hors ligne, tentative de servir offline.html');
                        return caches.match('/offline.html');
                    }
                    // Pour les autres types de requêtes (images, scripts, etc.) qui échouent hors ligne
                    // et ne sont pas dans le cache, on laisse l'erreur se propager
                    // ou on peut retourner un fallback générique (ex: une image par défaut).
                    console.error(`[Service Worker] Échec de la récupération pour ${event.request.url} et pas dans le cache.`);
                    // return new Response(null, { status: 503, statusText: 'Service Unavailable' }); // Optionnel
                });
            })
    );
});

// Événement 'activate' : le Service Worker prend le contrôle de la page
self.addEventListener('activate', event => {
    console.log('[Service Worker] Activation...');
    event.waitUntil(
        // Supprime les anciens caches si leur nom a changé (pour ne pas garder des versions obsolètes)
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => {
                    if (cacheName !== CACHE_NAME) { // SEUL le cache actuel est conservé
                        console.log('[Service Worker] Suppression de l\'ancien cache :', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
    console.log('[Service Worker] Actif et prêt à intercepter les requêtes.');
    return self.clients.claim(); // Rend le Service Worker actif pour tous les clients immédiatement après l'activation.
});