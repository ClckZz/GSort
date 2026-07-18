const { FusesPlugin } = require('@electron-forge/plugin-fuses');
const { FuseV1Options, FuseVersion } = require('@electron/fuses');

module.exports = {
  outDir: 'C:/GSort1',
  packagerConfig: {
    asar: false,
    ignore: [
      /^\/out($|\/)/,
      /^\/python-runtime($|\/)/,
      /\.git($|\/)/,
    ],
    extraResource: [
      './python-runtime',
      './main.py',
      './categorizer.py',
      './QuotesNEw.txt',
      './multi_class_model.pth',
    ],
  },
  rebuildConfig: {},
  makers: [
    {
      name: '@felixrieseberg/electron-forge-maker-nsis',
      config: {},
    },
    {
      name: '@electron-forge/maker-zip',
      platforms: ['darwin'],
    },
    {
      name: '@electron-forge/maker-deb',
      config: {},
    },
    {
      name: '@electron-forge/maker-rpm',
      config: {},
    },
  ],
  plugins: [
    // TEMPORÄR ENTFERNT - benötigt asar:true, testen wir gerade ohne
    // {
    //   name: '@electron-forge/plugin-auto-unpack-natives',
    //   config: {},
    // },
    // TEMPORÄR AUSKOMMENTIERT ZUM ISOLATIONSTEST
    // new FusesPlugin({
    //   version: FuseVersion.V1,
    //   [FuseV1Options.RunAsNode]: false,
    //   [FuseV1Options.EnableCookieEncryption]: true,
    //   [FuseV1Options.EnableNodeOptionsEnvironmentVariable]: false,
    //   [FuseV1Options.EnableNodeCliInspectArguments]: false,
    //   [FuseV1Options.EnableEmbeddedAsarIntegrityValidation]: true,
    //   [FuseV1Options.OnlyLoadAppFromAsar]: true,
    // }),
  ],
};