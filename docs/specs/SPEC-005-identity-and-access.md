# SPEC-005 — Identity and Access

## Smart Charging Experimentation Platform (SCEP)

**Status:** Approved

**Version:** 1.0

**Document Owner:** Project Team

**Last Update:** 2026

---

# 1. Purpose

This specification defines the **Identity and Access** capabilities of the Smart Charging Experimentation Platform.

Identity and Access provides:

* user management;
* authentication;
* role-based authorization;
* Facility-scoped access for operators;
* authentication for technical simulation clients;
* protection of existing and future API capabilities.

This specification introduces the security foundation required before operational workflows such as Reservations, Charging Sessions, Telemetry and Simulation are implemented.

---

# 2. Scope

This specification defines:

* user accounts;
* user lifecycle;
* technical client accounts;
* roles;
* multiple role assignment;
* Facility assignments;
* authentication with email and password;
* JWT access tokens;
* authorization rules;
* password requirements;
* REST API contracts;
* persistence model;
* protection of existing Facilities and Charging Stations endpoints;
* bootstrap of the first Platform Administrator;
* security validation;
* testing requirements;
* acceptance criteria.

This specification does not define:

* public user registration;
* refresh tokens;
* password recovery;
* email verification;
* multi-factor authentication;
* OAuth2 social login;
* external identity providers;
* OpenID Connect;
* API keys;
* frontend authentication screens;
* enterprise Single Sign-On;
* fine-grained attribute-based access control;
* production secrets management.

---

# 3. Business Context

Until this specification, SCEP APIs are accessible without authentication.

Identity and Access introduces the concept of an authenticated actor.

An actor may be:

* a human user;
* a technical client.

Human users interact with the platform according to their assigned roles.

Technical clients represent external automated components, such as the Digital Twin Simulation Engine.

Every protected operation must answer two questions:

1. Who is making the request?
2. Is that actor authorized to perform the requested operation?

Authentication establishes identity.

Authorization determines whether the authenticated identity may execute a capability.

---

# 4. Domain Concepts

## 4.1 User

A User represents a human identity that may access SCEP.

A User:

* has a unique identifier;
* has a unique email address;
* has a display name;
* has a password credential;
* has an account status;
* may have one or more Roles;
* may be associated with one or more Facilities;
* has creation and update timestamps.

---

## 4.2 Technical Client

A Technical Client represents a non-human identity used by an external automated system.

The initial Technical Client is the Digital Twin Simulation Engine.

A Technical Client:

- authenticates through the same token endpoint as Human accounts;
- is identified by the `TechnicalClient` account type;
- does not represent a person;
- does not receive Human Roles;
- cannot receive the `PlatformAdministrator` or `FacilityOperator` Roles;
- may access only capabilities explicitly granted to Technical Clients by the corresponding functional specifications.

For the first version, Technical Clients are stored using the same persistence model as Human Users and are differentiated by account type.

Technical Client permissions are derived from the account type rather than from a dedicated Role.

---

## 4.3 Role

A Role represents a set of platform capabilities.

A User may have multiple Roles.

Roles are assigned explicitly by a Platform Administrator.

Roles are not created dynamically in this version.

---

## 4.4 Facility Assignment

A Facility Assignment associates a Facility Operator with one or more Facilities.

The assignment limits management access to the Facilities that the operator is authorized to manage.

A Facility Operator without any Facility Assignment cannot manage Facility-scoped resources.

Platform Administrators are not restricted by Facility Assignments.

---

## 4.5 Access Token

An Access Token is a signed JWT issued after successful authentication.

The token represents the authenticated identity and contains the information required to enforce authorization.

The Access Token is short-lived and must be included in protected API requests.

---

# 5. User Attributes

A User shall contain:

* identifier;
* email;
* display name;
* password hash;
* account type;
* account status;
* roles;
* Facility Assignments;
* created timestamp;
* updated timestamp;
* last login timestamp.

The password itself shall never be persisted.

---

# 6. Account Type

Supported account types:

```text
Human
TechnicalClient
```

## Human

Represents a person who interacts with the platform.

## TechnicalClient

Represents an automated external system.

The first supported Technical Client is the Digital Twin Simulation Engine.

---

# 7. Account Status

Supported account statuses:

```text
Active
Inactive
```

## Active

The account may authenticate and access authorized capabilities.

## Inactive

The account cannot authenticate.

Previously issued tokens belonging to an inactive account must no longer authorize protected operations after the account status is checked.

Permanent account deletion is outside the scope of this specification.

---

# 8. Roles

The following Roles are defined for Human accounts.

## PlatformAdministrator

The Platform Administrator has unrestricted management access to the platform.

Responsibilities include:

- creating accounts;
- activating and deactivating accounts;
- assigning Roles to Human Users;
- assigning Facility access;
- managing all Facilities;
- managing all Charging Stations;
- managing all Connectors;
- viewing administrative account information.

---

## FacilityOperator

The Facility Operator manages charging infrastructure for assigned Facilities.

Responsibilities include:

- viewing assigned Facilities;
- updating assigned Facilities;
- creating Charging Stations in assigned Facilities;
- updating Charging Stations in assigned Facilities;
- adding Connectors;
- updating Connector status.

A Facility Operator cannot manage a Facility that is not explicitly assigned.

---

## EVDriver

The EV Driver represents a future consumer of Reservations and Charging Sessions.

In this specification, EV Drivers may authenticate and inspect their own identity.

Reservation and Charging Session permissions will be defined in SPEC-006 and SPEC-007.

---

## Researcher

The Researcher represents a user who performs experiments and analyzes platform behavior.

Research permissions will be defined by future Analytics, Dataset Export and Simulation specifications.

In this specification, Researchers may authenticate and inspect their own identity.

---

## DataScientist

The Data Scientist represents a user who works with datasets, predictions and AI experiments.

Dataset and prediction permissions will be defined in SPEC-011 and SPEC-012.

In this specification, Data Scientists may authenticate and inspect their own identity.

Technical Clients are not represented by a Role. Their permissions are defined directly from the `TechnicalClient` account type.

---

# 9. Role and Account-Type Rules

## BR-001 — Human Account Role

Every Active Human account shall have at least one Role.

Technical Client accounts are exempt from this rule.

---

## BR-002 — Multiple Roles

A Human User may have multiple Roles.

---

## BR-003 — Platform Administrator

A Platform Administrator may access all Facilities and charging infrastructure without Facility Assignments.

---

## BR-004 — Facility Operator Scope

A Facility Operator may manage only assigned Facilities and their Charging Stations and Connectors.

---

## BR-005 — Technical Client Restrictions

A Technical Client:

- shall not have Human Roles;
- shall not receive Facility Assignments;
- shall not manage Users;
- shall not manage Facilities, Charging Stations or Connectors;
- shall access only capabilities explicitly permitted to Technical Clients.

Future specifications may extend Technical Client permissions for simulation, telemetry, reservations and charging sessions.

---

## BR-006 — Role Management

Only Platform Administrators may assign or remove Roles from Human accounts.

---

## BR-007 — Self-Management Restriction

Users may inspect their own identity but may not change their own Roles or Facility Assignments.

Technical Clients may inspect their own identity but may not change their account configuration.

---

## BR-008 — Last Administrator Protection

The platform shall not allow the last Active Platform Administrator to be deactivated or to lose the `PlatformAdministrator` Role.

---

# 10. Permission Matrix

| Capability | Platform Administrator | Facility Operator | EV Driver | Researcher | Data Scientist | Technical Client |
|---|---:|---:|---:|---:|---:|---:|
| Authenticate | Yes | Yes | Yes | Yes | Yes | Yes |
| Read own identity | Yes | Yes | Yes | Yes | Yes | Yes |
| Create accounts | Yes | No | No | No | No | No |
| List accounts | Yes | No | No | No | No | No |
| Read any account | Yes | No | No | No | No | No |
| Update account status | Yes | No | No | No | No | No |
| Assign Roles | Yes | No | No | No | No | No |
| Assign Facilities | Yes | No | No | No | No | No |
| Create Facility | Yes | No | No | No | No | No |
| List Facilities | Yes | Assigned only | Active only | Read-only | Read-only | Active only |
| Read Facility | Yes | Assigned only | Active only | Read-only | Read-only | Active only |
| Update Facility | Yes | Assigned only | No | No | No | No |
| Create Station | Yes | Assigned only | No | No | No | No |
| List Stations | Yes | Assigned only | Active Facilities only | Read-only | Read-only | Active Facilities only |
| Read Station | Yes | Assigned only | Active Facilities only | Read-only | Read-only | Active Facilities only |
| Update Station | Yes | Assigned only | No | No | No | No |
| Add Connector | Yes | Assigned only | No | No | No | No |
| Update Connector Status | Yes | Assigned only | No | No | No | No |

"Assigned only" means that the target resource belongs to a Facility assigned to the authenticated Facility Operator.

"Active only" means that only resources belonging to Active Facilities are visible.

Technical Client permissions are based on `account_type`, not on a Role.

Future specifications may expand Technical Client permissions for simulation and telemetry workflows.

---

# 11. Authentication Flow

Authentication uses email and password.

The authentication flow is:

```text
Client

↓

POST /auth/login

↓

Credentials validated

↓

Account status validated

↓

JWT access token issued

↓

Client sends Authorization: Bearer <token>

↓

Token validated for protected requests
```

Authentication shall fail when:

* the email does not exist;
* the password is incorrect;
* the account is Inactive;
* the account has no valid Roles;
* the account type and assigned Roles are inconsistent.

Authentication failures must not reveal whether the email exists.

---

# 12. Token Model

The platform issues JWT Access Tokens.

The first version uses Access Tokens only.

Refresh Tokens are not supported.

## Token Lifetime

The default Access Token lifetime is:

```text
30 minutes
```

The lifetime shall be configurable through environment configuration.

## Required Claims

The token shall contain:

* `sub`: account identifier;
* `email`: normalized account email;
* `roles`: assigned Roles;
* `account_type`: account type;
* `iat`: issued-at timestamp;
* `exp`: expiration timestamp.

Facility Assignments shall not be embedded in the token.

Facility authorization must query current assignment information so that assignment changes take effect without waiting for token expiration.

## Token Validation

A protected request shall be rejected when:

* the token is missing;
* the token signature is invalid;
* the token is expired;
* required claims are missing;
* the account no longer exists;
* the account is Inactive;
* token Roles are no longer valid for the account.

---

# 13. Password Rules

Passwords shall:

* contain at least 12 characters;
* contain at least one uppercase letter;
* contain at least one lowercase letter;
* contain at least one numeric character;
* contain at least one special character;
* not contain the complete normalized email address;
* never be logged;
* never be returned by an API;
* never be persisted in plain text.

Password hashes shall be generated using a modern password-hashing algorithm appropriate for authentication credentials.

The exact library and hashing implementation are implementation decisions.

Password history, password expiration and compromised-password databases are outside the scope of this version.

---

# 14. Email Rules

Email addresses shall:

* be required;
* be syntactically valid;
* be normalized to lowercase;
* be unique regardless of case;
* not be changed in this version.

Duplicate normalized emails shall return `409 Conflict`.

---

# 15. User Lifecycle

The supported lifecycle is:

```text
Created as Active or Inactive

↓

Roles assigned

↓

Facility Assignments configured when required

↓

Authentication allowed when Active

↓

Account may be deactivated

↓

Account may be reactivated
```

Users shall not be physically deleted.

Deactivation preserves historical relationships and auditability.

---

# 16. Bootstrap Administrator

The first Platform Administrator shall be created through application bootstrap configuration.

Required environment variables:

```text
BOOTSTRAP_ADMIN_EMAIL
BOOTSTRAP_ADMIN_PASSWORD
BOOTSTRAP_ADMIN_DISPLAY_NAME
```

Bootstrap behavior:

* execute during application startup after database migrations;
* create the administrator only when no Platform Administrator exists;
* normalize the configured email;
* hash the configured password;
* assign the `PlatformAdministrator` role;
* create the account as Active;
* be idempotent;
* never overwrite an existing administrator;
* never log the configured password.

If a Platform Administrator already exists, the bootstrap configuration shall be ignored.

Bootstrap is intended for local development and initial installation.

Production credential provisioning is outside the scope of this specification.

---

# 17. REST API Contract

## 17.1 Login

```http
POST /auth/login
```

Request:

```json
{
  "email": "admin@scep.local",
  "password": "SecurePassword123!"
}
```

Response:

```json
{
  "access_token": "jwt-token",
  "token_type": "bearer",
  "expires_in": 1800
}
```

Responses:

* `200 OK`: authentication successful;
* `401 Unauthorized`: invalid credentials;
* `403 Forbidden`: account is Inactive.

---

## 17.2 Get Current Identity

```http
GET /auth/me
```

Response:

```json
{
  "id": "user-id",
  "email": "admin@scep.local",
  "display_name": "SCEP Administrator",
  "account_type": "Human",
  "status": "Active",
  "roles": [
    "PlatformAdministrator"
  ],
  "facility_ids": []
}
```

Responses:

* `200 OK`: authenticated identity returned;
* `401 Unauthorized`: missing or invalid token.

---

## 17.3 Create User

```http
POST /users
```

Required Role:

```text
PlatformAdministrator
```

Request:

```json
{
  "email": "operator@scep.local",
  "display_name": "Facility Operator",
  "password": "SecurePassword123!",
  "account_type": "Human",
  "status": "Active",
  "roles": [
    "FacilityOperator"
  ],
  "facility_ids": [
    "facility-id"
  ]
}
```

Response:

```json
{
  "id": "user-id",
  "email": "operator@scep.local",
  "display_name": "Facility Operator",
  "account_type": "Human",
  "status": "Active",
  "roles": [
    "FacilityOperator"
  ],
  "facility_ids": [
    "facility-id"
  ],
  "created_at": "timestamp",
  "updated_at": "timestamp",
  "last_login_at": null
}
```

Responses:

* `201 Created`: User created;
* `401 Unauthorized`: missing or invalid authentication;
* `403 Forbidden`: insufficient permission;
* `404 Not Found`: assigned Facility does not exist;
* `409 Conflict`: email already exists;
* `422 Unprocessable Entity`: invalid account data.

---

## 17.4 List Users

```http
GET /users
```

Required Role:

```text
PlatformAdministrator
```

Optional filters:

* status;
* role;
* account type.

Responses:

* `200 OK`;
* `401 Unauthorized`;
* `403 Forbidden`.

Password hashes shall never be returned.

---

## 17.5 Get User

```http
GET /users/{user_id}
```

Required Role:

```text
PlatformAdministrator
```

Responses:

* `200 OK`;
* `401 Unauthorized`;
* `403 Forbidden`;
* `404 Not Found`.

---

## 17.6 Update User Profile and Status

```http
PATCH /users/{user_id}
```

Required Role:

```text
PlatformAdministrator
```

Allowed fields:

* display name;
* account status.

Request:

```json
{
  "status": "Inactive"
}
```

Email and account type cannot be changed.

Responses:

* `200 OK`;
* `401 Unauthorized`;
* `403 Forbidden`;
* `404 Not Found`;
* `409 Conflict`: operation would remove the last Active Platform Administrator;
* `422 Unprocessable Entity`.

---

## 17.7 Replace User Roles

```http
PUT /users/{user_id}/roles
```

Required Role:

```text
PlatformAdministrator
```

Request:

```json
{
  "roles": [
    "FacilityOperator",
    "Researcher"
  ]
}
```

The supplied list replaces the complete current Role set.

Responses:

* `200 OK`;
* `401 Unauthorized`;
* `403 Forbidden`;
* `404 Not Found`;
* `409 Conflict`: operation would remove the last Active Platform Administrator;
* `422 Unprocessable Entity`.

---

## 17.8 Replace Facility Assignments

```http
PUT /users/{user_id}/facilities
```

Required Role:

```text
PlatformAdministrator
```

Request:

```json
{
  "facility_ids": [
    "facility-id-1",
    "facility-id-2"
  ]
}
```

The supplied list replaces all current Facility Assignments.

Responses:

* `200 OK`;
* `401 Unauthorized`;
* `403 Forbidden`;
* `404 Not Found`: User or Facility not found;
* `422 Unprocessable Entity`.

Facility Assignments are meaningful only for Users with the `FacilityOperator` role.

---

# 18. Authorization of Existing Endpoints

## Facilities

### Create Facility

```http
POST /facilities
```

Allowed:

```text
PlatformAdministrator
```

---

### List Facilities

```http
GET /facilities
```

Allowed:

* Platform Administrator: all Facilities;
* Facility Operator: assigned Facilities only;
* EV Driver: all Active Facilities, read-only;
* Researcher: all Facilities, read-only;
* Data Scientist: all Facilities, read-only;
* Technical Client: all Active Facilities, read-only.

---

### Get Facility

```http
GET /facilities/{facility_id}
```

Allowed:

* Platform Administrator: any Facility;
* Facility Operator: assigned Facilities only;
* EV Driver: Active Facilities only;
* Researcher: any Facility;
* Data Scientist: any Facility;
* Technical Client: Active Facilities only.

---

### Update Facility

```http
PUT /facilities/{facility_id}
```

Allowed:

* Platform Administrator;
* Facility Operator assigned to the target Facility.

---

## Charging Stations

### Create Charging Station

```http
POST /facilities/{facility_id}/stations
```

Allowed:

* Platform Administrator;
* Facility Operator assigned to the target Facility.

---

### List Charging Stations

```http
GET /facilities/{facility_id}/stations
```

Allowed:

* Platform Administrator;
* assigned Facility Operator;
* EV Driver for Active Facilities;
* Researcher;
* Data Scientist;
* Technical Client for Active Facilities.

---

### Get Charging Station

```http
GET /stations/{station_id}
```

Allowed according to the parent Facility access rules.

---

### Update Charging Station

```http
PATCH /stations/{station_id}
```

Allowed:

* Platform Administrator;
* Facility Operator assigned to the parent Facility.

---

### Add Connector

```http
POST /stations/{station_id}/connectors
```

Allowed:

* Platform Administrator;
* Facility Operator assigned to the parent Facility.

---

### Update Connector Status

```http
PATCH /connectors/{connector_id}/status
```

Allowed:

* Platform Administrator;
* Facility Operator assigned to the parent Facility.

---

# 19. Persistence Model

## users

```text
id
email
display_name
password_hash
account_type
status
created_at
updated_at
last_login_at
```

Constraints:

* primary key on `id`;
* case-insensitive unique normalized email;
* required password hash;
* valid account type;
* valid account status.

---

## roles

```text
id
name
```

Roles shall be seeded from the fixed Role definitions.

Constraints:

* unique role name.

---

## user_roles

```text
user_id
role_id
created_at
```

Constraints:

* composite unique constraint on `user_id` and `role_id`;
* foreign key to Users;
* foreign key to Roles.

---

## user_facilities

```text
user_id
facility_id
created_at
```

Constraints:

* composite unique constraint on `user_id` and `facility_id`;
* foreign key to Users;
* foreign key to Facilities.

---

# 20. Security Rules

## SR-001 — Password Protection

Passwords and password hashes shall never appear in API responses, logs or error messages.

---

## SR-002 — Generic Authentication Failure

Invalid email and invalid password shall produce the same external authentication error.

---

## SR-003 — Protected-by-Default

New API endpoints shall be protected by default unless a specification explicitly marks them as public.

---

## SR-004 — Public Endpoints

The following endpoints remain public:

```text
GET /health
GET /health/live
GET /health/ready
GET /metrics
GET /docs
GET /openapi.json
POST /auth/login
```

Access to `/metrics`, `/docs` and `/openapi.json` may be restricted in a future deployment specification.

---

## SR-005 — Token Secret

The JWT signing secret shall be provided through environment configuration.

It shall not be committed to source control.

---

## SR-006 — Authorization Enforcement

Authorization must be enforced in application or security services, not only through UI behavior.

---

## SR-007 — Current Account Validation

Protected operations must validate that the account remains Active.

---

## SR-008 — No Sensitive Logging

Authentication requests, passwords, complete tokens and signing secrets shall not be logged.

---

# 21. Environment Configuration

The implementation shall support:

```text
JWT_SECRET_KEY
JWT_ACCESS_TOKEN_EXPIRE_MINUTES
BOOTSTRAP_ADMIN_EMAIL
BOOTSTRAP_ADMIN_PASSWORD
BOOTSTRAP_ADMIN_DISPLAY_NAME
```

`.env.example` shall contain safe local-development examples.

Real credentials shall remain in `.env`, which is ignored by Git.

---

# 22. Error Handling

Authentication and authorization use the following status codes:

* `401 Unauthorized`: authentication is missing or invalid;
* `403 Forbidden`: identity is valid but lacks permission;
* `404 Not Found`: requested resource does not exist or is not visible to the actor;
* `409 Conflict`: uniqueness or administrator-protection conflict;
* `422 Unprocessable Entity`: invalid payload or business validation failure.

For Facility-scoped resources, implementations may return `404` instead of `403` when revealing resource existence would disclose unauthorized information.

The behavior must remain consistent across equivalent endpoints.

---

# 23. Testing Requirements

Tests shall cover:

## Domain

* User creation;
* email normalization;
* password-rule validation;
* account status;
* multiple Roles;
* Technical Client restrictions;
* last Active Platform Administrator protection;
* Facility Assignment rules.

## Authentication

* successful login;
* incorrect email;
* incorrect password;
* inactive account;
* expired token;
* invalid signature;
* missing claims;
* missing token;
* current identity retrieval;
* last login update.

## Authorization

* Platform Administrator access;
* Facility Operator assigned access;
* Facility Operator unassigned access rejection;
* read-only role access;
* Technical Client restrictions;
* insufficient Role rejection;
* deactivated account token rejection.

## User Management

* create User;
* duplicate normalized email;
* list Users;
* get User;
* update account status;
* replace Roles;
* replace Facility Assignments;
* prevent last administrator deactivation;
* prevent last administrator Role removal;
* password and hash never exposed.

## Existing APIs

* Facilities endpoints protected;
* Charging Stations endpoints protected;
* Connector endpoints protected;
* Facility-scoped authorization enforced;
* public health and authentication endpoints remain accessible.

## Persistence

* User persistence;
* unique normalized email;
* Role relations;
* Facility Assignment relations;
* account updates;
* Alembic migration upgrade and downgrade;
* bootstrap administrator idempotency.

## OpenAPI

* bearer authentication scheme is present;
* protected endpoints declare authentication;
* public endpoints remain public;
* request and response models do not expose password hashes.

---

# 24. Observability Requirements

The implementation shall expose security-related operational information without exposing sensitive data.

Allowed observations include:

* successful authentication count;
* failed authentication count;
* authorization-denied count;
* account creation count;
* inactive-account authentication attempts.

Metrics and logs must not include:

* passwords;
* password hashes;
* complete JWTs;
* JWT secrets;
* sensitive credential values.

Audit-log persistence is deferred to a future specification.

---

# 25. Deferred Work

The following capabilities are deferred:

* refresh tokens;
* token revocation lists;
* password recovery;
* password change by Users;
* email verification;
* multi-factor authentication;
* account lockout;
* rate limiting;
* OAuth2 providers;
* OpenID Connect;
* enterprise identity providers;
* audit-log persistence;
* production secrets management;
* API keys;
* dynamic Roles;
* custom Permissions;
* frontend authentication;
* session management across devices.

---

# 26. Acceptance Criteria

This specification is complete when:

* Users can be created by a Platform Administrator;
* email addresses are normalized and unique;
* passwords are securely hashed;
* Active Users can authenticate;
* Inactive Users cannot authenticate;
* JWT Access Tokens are issued and validated;
* Users can inspect their own identity;
* Users may have multiple Roles;
* Platform Administrators can manage Roles;
* Platform Administrators can manage Facility Assignments;
* Facility Operators are restricted to assigned Facilities;
* existing Facilities endpoints are protected;
* existing Charging Stations and Connectors endpoints are protected;
* Technical Clients authenticate as technical accounts;
* the first Platform Administrator can be bootstrapped safely;
* the last Active Platform Administrator is protected;
* sensitive credential data is never returned or logged;
* OpenAPI documents bearer authentication;
* persistence and migrations are implemented;
* automated tests validate authentication and authorization;
* Docker Compose smoke tests validate the complete authentication flow;
* Domain Events remain deferred to SPEC-009.

---

# 27. Implementation Notes

This specification defines functional behavior and security requirements.

The implementation may select appropriate libraries for:

* JWT creation and validation;
* password hashing;
* FastAPI authentication dependencies;
* email validation.

Library selection shall not change the behavior defined by this specification.

A new ADR is required only if implementation introduces a broader architectural security decision not already covered by the current architecture baseline.
