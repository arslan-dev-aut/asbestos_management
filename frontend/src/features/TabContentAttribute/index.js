import { createApp } from "vue";
import MainComponent from './index.vue'
import '../../assets/style.css';

export const mountApp = (holder, context) => {
    const app = createApp(MainComponent, {
        modelData: context.model
    });

    // Add global property for emitting to parent
    app.config.globalProperties.$emitToParent = (eventKey, payload) => {
        if (!holder?.dispatchEvent) return
        const martketplaceEvent = new CustomEvent(eventKey, payload || {});
        holder.dispatchEvent(martketplaceEvent)
    };

    return app.mount(holder);
};
