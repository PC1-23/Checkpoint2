# ADR 0002: Password Hashing Method

Date: 2025-09-14

## Status
Accepted

## Context
Initial demo users were hashed with an algorithm that caused environment-specific errors (e.g., scrypt not available in some Python/OpenSSL builds). We need a broadly compatible algorithm.

## Decision
Use `pbkdf2:sha256` (Werkzeug `generate_password_hash(..., method="pbkdf2:sha256")`) for user passwords in seeding and registration.

## Consequences
- Works reliably across environments.
- If prior users used an unsupported hash, reseeding updates demo users; login route handles errors gracefully and prompts reset.
