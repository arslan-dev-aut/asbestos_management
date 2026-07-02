import { exec } from "child_process";
import path, { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import { build } from "vite";

const features = [
  {
    key: "AsbestosLibrary",
    path: "src/features/AsbestosLibrary/index.js",
  },
  {
    key: "TabContentAttribute",
    path: "src/features/TabContentAttribute/index.js",
  },
  {
    key: "TabItemRequests",
    path: "src/features/TabItemRequests/index.js",
  }
];

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

async function runBuildScript(feature, modeEnv) {
  try {
    console.log(`Building feature: ${feature.key} ${feature.path}...`);

    // Configure Vite build options
    const config = {
      configFile: "vite-feature.config.js",
      mode: modeEnv || "embed",
      publicDir: 'publicFeature',
      build: {
        minify: false,
        lib: {
          // Could also be a dictionary or array of multiple entry points
          entry: resolve(__dirname, feature.path),
          name: feature.key,
          // the proper extensions will be added
          fileName: "index",
          formats: ["es"],
        },
        // Write into dist/ so the file is included in the Docker image
        // (which COPYs /app/dist only). Writing into public/ here is too late
        // because the main `vite build` has already copied public/ to dist/.
        outDir: `dist/feature/${feature.key}`,
        // watch: {
        //   // Use chokidar settings for build watch (like dev server)
        //   // Polling option for CI environments
        //   usePolling: true,
        // },
      },
    };

    // Run the Vite build
    await build(config);

    console.log(`Build completed for ${feature.key}`);
  } catch (error) {
    console.error("Failed to build the feature:", error);
    throw error;
  }
}

async function runBuildCommand(feature) {
  return new Promise((resolve, reject) => {
    // console.log(`Building feature: ${feature.key}...`);

    // Linux ENV_VAR=value npm run build
    // Docker docker build --build-arg ENV_VAR=value -t my-image .
    exec(
      `set FEATURE_INFO=${JSON.stringify(
        feature
      )} && vite build --config vite-feature.config.js --mode embed`,
      {},
      (error, stdout, stderr) => {
        if (error) {
          console.error(`Error building ${feature.key}: ${stderr}`);
          reject(error);
        } else {
            console.log(`Output for ${feature.key}: ${stdout}`);
          resolve();
        }
      }
    );
  });
}

export async function buildAllProjects(modeEnv) {
  for (const feature of features) {
    try {
      await runBuildScript(feature, modeEnv);
    } catch (error) {
      // console.error(`Failed to build ${feature.key}:`, error);
      process.exit(1);
    }
  }

  // console.log("All features built successfully!");
}
