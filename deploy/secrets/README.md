# Runtime secrets

Create these local files before starting the production Compose stack. They are intentionally ignored by Git:

- `postgres_password.txt`
- `database_url.txt` — for example, a PostgreSQL URL with `sslmode=require` when the database supports TLS
- `redis_password.txt`
- `redis_url.txt` — an authenticated Redis URL
- `jwt_secret.txt` — at least 32 random characters
- `data_encryption_key.txt` — a Fernet key generated with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

Never commit the values. Production integrations should be injected by the platform's secret manager using the corresponding environment variables.
