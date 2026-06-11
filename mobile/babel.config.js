module.exports = function (api) {
  api.cache(true);
  return {
    // babel-preset-expo (SDK 55) 自动包含 expo-router 支持 + react-native-worklets/plugin
    // (reanimated v4 所需),无需手动再加 worklets 插件,否则会重复报错。
    presets: ["babel-preset-expo"],
  };
};
