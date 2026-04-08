import dag_cbor
from multiformats import CID, multihash
import json
import hashlib


def generateCid(data: dict) -> str:
    try:
        encoded_bytes = dag_cbor.encode(data)
        hash_bytes = hashlib.sha256(encoded_bytes).digest()
        mh = multihash.wrap(hash_bytes, "sha2-256")
        cid = CID(version=1, codec="dag-cbor", digest=mh, base="base32")
        return str(cid)

    except Exception as e:
        print(f"Error al convertir CID: {e}")
        raise e
