# API Client Collections

## Insomnia

Import `scep-insomnia.json` into Insomnia using **Import → File**.

The collection provides requests for health, metrics, authentication, users, facilities,
charging stations and connectors. Its base environment points to `http://localhost:8000`
and uses the bootstrap administrator credentials from `.env.example`.

Before calling protected endpoints:

1. run **Authentication → Login**;
2. copy `access_token` from the response;
3. edit the collection environment and set `access_token`;
4. after creating resources, copy their identifiers into `user_id`, `facility_id`,
   `station_id` or `connector_id` as appropriate.

Do not commit real access tokens or non-local credentials to this file.
