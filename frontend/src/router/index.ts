import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/asbestos-register',
    },
    {
      path: '/asbestos-register',
      name: 'asbestos-register',
      component: () => import('@/views/AsbestosRegister.vue'),
    },
    {
      path: '/asbestos-register/:asbestosSiteId',
      name: 'site-detail',
      component: () => import('@/views/SiteDetail.vue'),
      props: true,
    },
    {
      // Read-only Customer Portal preview of a site's Asbestos tab (standalone chrome)
      path: '/portal-preview/:asbestosSiteId',
      name: 'customer-portal-preview',
      component: () => import('@/views/CustomerPortalPreview.vue'),
      props: true,
      meta: { public: true },
    },
    {
      // Standalone read-only portal tab — no top chrome, no site selector.
      // Embedded by Customer / Main Contractor / Subcontractor portals via iframe
      // or linked directly as /portal/:asbestosSiteId/asbestos.
      path: '/portal/:asbestosSiteId/asbestos',
      name: 'portal-site-view',
      component: () => import('@/views/PortalSiteView.vue'),
      props: true,
      meta: { public: true },
    },
    {
      // Public, login-free QR view — rendered standalone (no app shell)
      path: '/site/:token/asbestos',
      name: 'public-site-view',
      component: () => import('@/views/PublicSiteView.vue'),
      props: true,
      meta: { public: true },
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('@/views/NotFound.vue'),
    },
  ],
})

export default router
