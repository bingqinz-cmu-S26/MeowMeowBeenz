const appJson = require('./app.json');

const isWebStart = process.argv.some((arg) => arg === '--web' || arg.startsWith('--web'));

module.exports = () => {
  const plugins = appJson.expo.plugins.filter((plugin) => {
    const name = Array.isArray(plugin) ? plugin[0] : plugin;
    if (isWebStart && name === '@livekit/react-native-webrtc') {
      return false;
    }
    return true;
  });

  return {
    ...appJson.expo,
    plugins,
  };
};
