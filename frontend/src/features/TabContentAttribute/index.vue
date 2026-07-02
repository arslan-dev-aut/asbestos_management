<template>
    <div id="asbestosTab" role="tabpanel" class="tab-pane fade">
        <div id="assignedAttributesVM">
            <SiteDetail :asbestosSiteId="siteId"/>
        </div>
    </div>
</template>

<script>
import SiteDetail from '@/views/SiteDetail.vue';

export default {
    name: "AsbestosIntegrationFeature",
    components: { SiteDetail },
    data() {
        return {
            siteId: null
        }
    },
    mounted() {
        this.extractSiteIdFromUrl();
    },
    methods: {
        extractSiteIdFromUrl() {
            const url = window.location.href;
            const match = url.match(/\/Site\/Detail\/(\d+)/);
            this.siteId = match ? match[1] : null;
        }
    }
}
</script>