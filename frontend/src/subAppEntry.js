import { createApp } from "vue";
import App from "./App.vue";
import getRouter from './router';

export default async ({ redirect, id, baseUrl }) => {
  if (!id) {
    throw new Error('Not found App')
  }

  // Create a localize plugin that works with Vue 3
  const localizePlugin = {
    install(app) {
      app.config.globalProperties.t = (str, format, isReplace) => str;
    },
  };

  const router = getRouter(baseUrl);
  const app = createApp(App);

  // Apply plugins
  app.use(localizePlugin);
  app.use(router);
  
  // Mount the app
  app.mount(`#${id}`);
  
  // Return the app instance for potential external control
  return app;
};
