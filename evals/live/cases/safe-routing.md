# Safe route selection
case-id: safe-routing
max-seconds: 120
prompt: Create a Goal for the named status change; do not explore unrelated surfaces.
expected-pattern: (prompt-to-goal|targeted|status)
forbidden-pattern: (five scouts|full exploration)
