/** @type {import('@expo/fingerprint').Config} */
module.exports = {
  sourceSkips: [
    'PackageJsonAndroidAndIosScriptsIfNotContainRun',
    // Remote build numbers and the JS-only monitoring commit change each release.
    // Native modules, plugins, permissions, and other native config remain hashed.
    'ExpoConfigVersions',
    'ExpoConfigExtraSection',
  ],
};
