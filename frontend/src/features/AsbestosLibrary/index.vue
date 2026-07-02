<template>
    <div class="col-xs-12 col-md-4 library-item-wrapper flex">
        <a class="library-item" 
           :href="stockConfigurationUrl">
            <i class="jli jl-file-chart"></i>
            <div>
                <h4>
                    <span class="jl-localization jl-localized">Asbestos Register</span>
                </h4>
                <p>
                    <span class="jl-localization jl-localized">
                        Manage the asbestos register across all sites. Track ACMs, risk scores, and compliance documentation.
                    </span>
                </p>
            </div>
        </a>
    </div>
</template>

<script>

export default {
    name: "StockConfigurationCard",
    data() {
        return {};
    },
    computed: {
        stockConfigurationUrl() {
            return `/Marketplace/${import.meta.env.VITE_APP_ID}/`;
        }
    },
    mounted() {}
}
</script>
