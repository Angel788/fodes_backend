# FODES API Server

The FODES API is a modular FastAPI application responsible for user authentication, metadata indexing, and content rating governance.

## Features

- **Modular Architecture:** Logic separated into `routers/` (Auth, Publications, Comments, Network).
- **Security:** JWT-based authentication and Bcrypt password hashing.
- **Rate Limiting:** Protects endpoints from abuse using `slowapi`.
- **Hybrid Storage:** Links MySQL metadata indexing with P2P CIDs.
- **Ponderated Voting:** 0-5 rating system with batch retrieval support.

## Configuration

The server uses a `.env` file in the root directory:

```env
SECRET_KEY="..."
DB_USER="root"
DB_PASSWORD="..."
DB_HOST="127.0.0.1"
DB_NAME="FODES2"
REDIS_HOST="localhost"
BOOTSTRAP_DIR="../NETWORK"
PSK_PATH="psk.key"
```

## API Endpoints

### Authentication
- `POST /register`: New user registration.
- `POST /login`: Get access token.

### Publications
- `POST /publications`: Index new content (generates CID).
- `GET /publications/search-cids`: Filter by category or tags.
- `POST /publications/vote`: Submit 0-5 rating.
- `POST /publications/rating`: Batch get average ratings.

### Comments
- `POST /comments`: Add comment to a publication CID.
- `GET /comments/publication/{cid}`: List comments.
- `POST /comments/rating`: Batch get comment ratings.

### Network
- `GET /network/bootstrap-info`: Get P2P multiaddr and PSK.

## Testing

Run the asynchronous test suite (requires a running server):
```bash
python tests/test_api.py
```
