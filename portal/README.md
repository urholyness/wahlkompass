# Curation & Coder Portal

This package contains the FastAPI backend and admin interface for paired statement coding and bill-to-statement mapping review.

## Features

1. **Statement CRUD**: Admin dashboard to manage statements, easy-German translations, and topic balances.
2. **Bill-to-Statement Mapping**: Tooling for coders to link Bundestag legislative bills to policy statements.
3. **Paired Coding Protocol**: Double-blind entry of T2/T3/T4 evidence, automatically surfacing inter-coder disagreements $> 0.5$ for methodology board resolution.
4. **Audit Trail**: Strict, append-only database audit log recording all human classification actions.
