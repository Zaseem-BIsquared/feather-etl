---
id: "6a18fddb-b214-4821-b0bb-81b74415e06b"
type: "template"
title: "API Feature"
status: "released"
owner: "system"
created: "2026-04-10"
updated: "2026-04-10"
description: "Feature template for REST API endpoints"
isSystemTemplate: true
templateFor: "feature"
---

# {{TITLE}}

## Overview

Description of this API feature and its purpose.

## Endpoints

### `GET /resource`

**Description:** Retrieve resources

**Request:**
- Headers: `Authorization: Bearer <token>`
- Query params: `?limit=10&offset=0`

**Response:**
```json
{
  "data": [],
  "total": 0
}
```

### `POST /resource`

**Description:** Create a new resource

**Request Body:**
```json
{
  "name": "string",
  "description": "string"
}
```

**Response:** 201 Created

## Error Handling

| Status | Description |
|--------|-------------|
| 400 | Invalid request body |
| 401 | Unauthorized |
| 404 | Resource not found |
| 500 | Internal server error |

## Security Considerations

- Authentication required
- Rate limiting: 100 requests/minute
