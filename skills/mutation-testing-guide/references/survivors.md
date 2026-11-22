# From surviving mutant to better test

For each survivor ask: **what observable behaviour does this change, and which test
should have noticed?** Then add the smallest assertion that fails on the mutant.

| Mutator (names vary by tool) | Example | What it reveals | Typical fix |
| --- | --- | --- | --- |
| Boundary / EqualityOperator / ConditionalBoundary | `>` -> `>=` | No test at the boundary value | Add the exact boundary case (100) and one each side |
| Negated conditional / ConditionalExpression | `if (a)` -> `if (true)` | Only one branch asserted | Test the false branch's outcome |
| Arithmetic | `*` -> `/`, `+` -> `-` | Result not asserted precisely (e.g. only `> 0`) | Assert the exact value |
| Return value / ArrowFunction / BlockStatement | function body emptied, returns null | Return value never checked | Assert on the return value |
| Method call removal / VoidMethodCall | `save()` removed | Side effect not verified | Assert the state change or the boundary call |
| Boolean / TrueValue / FalseValue | `return true` -> `false` | Caller's behaviour on this flag untested | Test both results |
| String literal | `"EUR"` -> `""` | Text not asserted (often fine) | Assert if it matters (currency code), otherwise ignore the mutator for logs |
| Array / ArrayDeclaration | `[a, b]` -> `[]` | Only length or truthiness checked | Assert contents |
| Logical operator | `&&` -> `\|\|` | Combined conditions not tested separately | Decision table: each condition true/false |
| Regex | `^\d+$` -> `\d+$` | Validation edge cases missing | Add an input that only the stricter regex rejects |
| Increment / Decrement | `i++` -> `i--` | Loop result not asserted (or Timeout, which is fine) | Assert the collection result |
| Visibility (Infection) | `public` -> `protected` | Method is not used publicly | Consider making it non-public |

## Equivalent mutants

Some mutants cannot change behaviour (e.g. `>=` vs `>` when the equal case is
impossible, or a mutated log message). Do not write contorted tests for them:

- Stryker: `// Stryker disable next-line <Mutator>: reason`
- Infection: mutator `ignore` entries or `@infection-ignore-all`
- mutmut: `# pragma: no mutate` on the line

Always write the reason; reviewers should be able to agree it is equivalent.

## Worked example

```js
export function discount(total) {
  if (total > 100) return total * 0.9;
  return total;
}
// existing test
expect(discount(200)).toBeLessThan(200);
```

Survivors: `total > 100` -> `total >= 100` (no test at exactly 100) and
`if (total > 100)` -> `if (true)` (no test below the threshold). The arithmetic mutant
`total * 0.9` -> `total / 0.9` is killed because 222 is not less than 200. Fix with exact
values below, at and above the boundary:

```js
it.each([[50, 50], [100, 100], [100.01, 90.009], [200, 180]])('discount(%d) = %d', (input, expected) => {
  expect(discount(input)).toBeCloseTo(expected);
});
```
