# API Standards

## Request and response validation

- Use Pydantic request and response schemas.
- Keep domain models separate from HTTP DTOs.
- Route handlers return typed response models or typed dictionaries.

## Error handling

- Use a typed exception hierarchy.
- Register centralized exception handlers.
- Return actionable error messages.
- Use consistent HTTP status codes.

## Access enforcement

- Keep routes thin.
- Use dependencies for auth and scoped access.
- Leave health routes unauthenticated.

## Recommended status codes

- `200` success
- `201` created
- `400` validation failure
- `401` missing auth
- `403` forbidden
- `404` not found
- `409` conflict
- `422` invalid state or semantic request issue
- `429` rate limited
- `502` upstream or database failure