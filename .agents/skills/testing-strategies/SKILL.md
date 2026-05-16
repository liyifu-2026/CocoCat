---
name: testing-strategies
description: Comprehensive testing strategy design covering unit, integration, E2E testing, and TDD practices. Use when defining a testing strategy, before refactoring, when bugs happen frequently, or when setting up CI/CD automated tests.
---

# Testing Strategies

## When to use this skill

- **New project**: define a testing strategy
- **Quality issues**: bugs happen frequently
- **Before refactoring**: build a safety net
- **CI/CD setup**: automated tests

## Instructions

### Step 1: Understand the Test Pyramid

Structure tests according to the test pyramid with recommended ratios:

- **70% Unit tests**: Fast, isolated tests for individual functions/modules. No external dependencies.
- **20% Integration tests**: Test interactions between modules, APIs, and databases.
- **10% E2E tests**: Full user flow validation through the UI. Slowest but highest confidence.

### Step 2: Unit Testing

Use the **Given-When-Then** pattern:

```
Given: Set up preconditions and test data
When: Execute the action being tested
Then: Assert the expected outcomes
```

Also follow the **AAA pattern** (Arrange, Act, Assert):

```
// Arrange - set up test state
const user = { name: "Alice", age: 30 };

// Act - execute the code under test
const result = validateUser(user);

// Assert - verify the outcome
expect(result).toBe(true);
```

#### Mocking strategies for external dependencies

- **Mock at boundaries**: Mock HTTP clients, database drivers, file system — not internal modules.
- **Use test doubles appropriately**:
  - **Stubs**: Return canned answers (e.g., a stubbed API response).
  - **Mocks**: Verify behavior (e.g., `expect(mockFn).toHaveBeenCalledWith(...)`).
  - **Fakes**: Lightweight working implementations (e.g., in-memory database).
- **Avoid mocking what you don't own**: Wrap third-party APIs in your own adapter, mock the adapter.

### Step 3: Integration Testing

Test interactions between real components:

- Database integration: Use a test database or in-memory alternative. Seed known data before each test. Clean up after.
- API endpoint testing: Send real HTTP requests to the running service. Verify status codes, response bodies, and headers.

API endpoint testing example pattern:

```
Given: A seeded database with 3 products
When: GET /api/products
Then: Response status is 200, body contains exactly 3 products
```

### Step 4: E2E Testing

Use **Playwright** (or Cypress) for complete user flow validation:

- Test critical user journeys only (login, checkout, onboarding).
- Run against a fully deployed environment (staging/CI).
- Use data-testid attributes for selectors (not CSS classes or text content).
- Keep E2E tests independent — each test sets up its own state.

### Step 5: TDD (Test-Driven Development)

Follow the **red-green-refactor** cycle:

1. **Red**: Write a failing test that describes the desired behavior.
2. **Green**: Write the minimum code to make the test pass.
3. **Refactor**: Clean up the code while keeping tests green.

### Step 6: CI/CD Integration

- Run unit + integration tests on every push and PR.
- Run E2E tests on merge to main or before deployment.
- Fail the build if coverage drops below threshold.
- Use test parallelization for speed.
- Flaky tests should be immediately quarantined and fixed.

### Step 7: Test Isolation and Best Practices

- **Deterministic tests**: No random data, no time-dependent assertions, no shared mutable state.
- **Test isolation**: Each test must be independent — order must not matter.
- **Edge case handling**: Test empty inputs, boundary values, error paths, null/undefined.
- **One assertion concept per test** (or closely related assertions).
- **Descriptive test names**: Use `describe`/`it` blocks that form readable sentences.
- **Fast feedback**: Unit tests should complete in milliseconds; the full suite in under 5 minutes.

### Quick Decision Guide

| Scenario | Action |
|----------|--------|
| New function or module | Write unit tests (Given-When-Then, AAA) |
| API endpoint or DB query | Write integration tests |
| Critical user flow | Write E2E tests |
| Fixing a bug | Write a regression test first |
| Before refactoring | Ensure existing tests pass, add missing coverage |
| Flaky test found | Quarantine immediately, fix within 24h |
