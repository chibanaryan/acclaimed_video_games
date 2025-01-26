const { defineConfig } = require('@vue/cli-service')
module.exports = defineConfig({
  configureWebpack: {
    devtool: 'source-map'
  },
  transpileDependencies: true,
  assetsDir: "static",
  outputDir: "./dist/",
  devServer: {
    proxy: {
      "^/api/": {
        target: "http://127.0.0.1:8000/api/",
        ws: false,
      },
    },
  },
})
