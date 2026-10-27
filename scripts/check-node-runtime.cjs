// npm lifecycle hooks are disabled in this repository, so invoke this guard
// explicitly from each development/build/test command.
function isSupportedNode(version) {
  const match = /^v?24\.(\d+)\.(\d+)$/.exec(version);
  return !!match && (Number(match[1]) > 22 ||
    (Number(match[1]) === 22 && Number(match[2]) >= 1));
}

if (require.main === module && !isSupportedNode(process.version)) {
  console.error(`Patched Node >=24.22.1 <25 is required; found ${process.version}. Run nvm use from the repository (nvm install if needed).`);
  process.exitCode = 1;
}

module.exports = { isSupportedNode };
