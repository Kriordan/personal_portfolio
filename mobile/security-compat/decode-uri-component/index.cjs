// query-string 7 expects a callable CommonJS export. Node 24 and Metro both
// expose the patched upstream ESM decoder through its default export.
module.exports = require('decode-uri-component-upstream').default;
