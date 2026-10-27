// Expo 57's CLI/MCP integrations still require the Zod 3 schema interface.
// Backport early collection rejection to the pinned upstream compatibility
// API. Keep the fixed Zod 4 implementation for consumers that support it.
const zod = require('zod-upstream/v3');
const budgetKey = Symbol('portfolio.cli.collection-budget');
const maximumEntries = 1000;

// Initialize before unions/catch schemas clone their common context. Their
// shallow copies then share the same budget object, including in async parses.
const processInputParams = zod.ZodType.prototype._processInputParams;
zod.ZodType.prototype._processInputParams = function (input) {
  const result = processInputParams.call(this, input);
  result.ctx.common[budgetKey] ??= { remaining: maximumEntries };
  return result;
};

for (const [Schema, type, size, bounds] of [
  [zod.ZodArray, 'array', value => Array.isArray(value) ? value.length : -1,
    def => [[def.exactLength, true], [def.maxLength, false]]],
  [zod.ZodSet, 'set', value => value instanceof Set ? value.size : -1,
    def => [[def.maxSize, false]]],
  [zod.ZodMap, 'map', value => value instanceof Map ? value.size : -1,
    () => []],
]) {
  const originalParse = Schema.prototype._parse;
  Schema.prototype._parse = function (input) {
    const count = size(input.data);
    if (count < 0) return originalParse.call(this, input);
    const { ctx } = this._processInputParams(input);

    // Match the upstream size-gate fix: never parse elements or run later
    // refinements when an upper bound already rejects the raw collection.
    for (const [bound, exact] of bounds(this._def)) {
      if (bound && count > bound.value) {
        zod.addIssueToContext(ctx, {
          code: 'too_big', maximum: bound.value, type, inclusive: true,
          exact, message: bound.message,
        });
        return zod.INVALID;
      }
    }

    // Expo's plugin schemas also contain unconstrained arrays. One budget
    // bounds all collection work, and each independent parse starts fresh.
    const budget = ctx.common[budgetKey];
    if (count > budget.remaining) {
      zod.addIssueToContext(ctx, {
        code: 'custom',
        message: `Expo tooling input exceeds the ${maximumEntries}-entry collection budget`,
      });
      return zod.INVALID;
    }
    budget.remaining -= count;
    return originalParse.call(this, input);
  };
}

module.exports = zod;
