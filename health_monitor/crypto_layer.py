"""
End-to-End Cryptographic Security & Anti-Spoofing Telemetry Protection.

Implements military/space-grade cryptographic safeguards:
1. AES-256-GCM Authenticated Encryption with Associated Data (AEAD)
2. RFC 5869 HKDF Key Derivation (zero hardcoded secrets)
3. Cryptographic Token Authentication with HMAC-SHA256
4. Monotonic Nonce Generation & Anti-Replay Sliding Window
5. Constant-time digest verification against timing attacks
"""

import os
import time
import json
import struct
import hmac
import hashlib
import logging
from typing import Dict, Any, Tuple, Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

from health_monitor.config import SecurityConfig

logger = logging.getLogger("CryptoSecurity")

class CryptoEngine:
    """Manages AES-256-GCM encryption, decryption, and key derivation."""

    SALT_TELEMETRY = b"ASTRONAUT_TELEMETRY_E2EE_V1"
    SALT_AUTH_TOKEN = b"ASTRONAUT_TOKEN_AUTH_V1"

    def __init__(self, master_key: Optional[bytes] = None):
        if master_key is None:
            master_key = SecurityConfig.get_master_key()

        # Derive dedicated AES-256 encryption key via HKDF
        hkdf_enc = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.SALT_TELEMETRY,
            info=b"suit-edge-encryption-key",
        )
        self._enc_key = hkdf_enc.derive(master_key)
        self._aesgcm = AESGCM(self._enc_key)

        # Derive dedicated HMAC token signing key
        hkdf_token = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.SALT_AUTH_TOKEN,
            info=b"suit-token-signing-key",
        )
        self._token_key = hkdf_token.derive(master_key)

        # 4-byte random instance prefix + 8-byte monotonic counter for 12-byte IV
        self._node_salt = os.urandom(4)
        self._seq_counter = 0

        # Anti-replay sliding window (tracks highest seen seq and recent set)
        self._highest_seq = 0
        self._seen_seqs: set[int] = set()
        self._replay_window_size = 2048

    def _generate_nonce(self) -> Tuple[bytes, int]:
        """Generates a strictly unique 12-byte (96-bit) nonce per packet."""
        self._seq_counter += 1
        seq = self._seq_counter
        # Pack 4 bytes node salt + 8 bytes uint64 sequence counter = 12 bytes
        nonce = self._node_salt + struct.pack(">Q", seq)
        return nonce, seq

    def encrypt_telemetry(self, astronaut_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Encrypts telemetry dictionary using AES-256-GCM.
        Binds astronaut_id and timestamp into Authenticated Associated Data (AAD).
        """
        timestamp_ms = int(time.time() * 1000)
        nonce, seq_num = self._generate_nonce()

        # Associated Data binds the packet header cryptographically
        aad = f"{astronaut_id}:{timestamp_ms}:{seq_num}".encode("utf-8")
        plaintext = json.dumps(payload, sort_keys=True).encode("utf-8")

        # AES-GCM produces ciphertext + 16-byte authentication tag
        ciphertext_with_tag = self._aesgcm.encrypt(nonce, plaintext, aad)

        return {
            "astronaut_id": astronaut_id,
            "timestamp_ms": timestamp_ms,
            "seq_num": seq_num,
            "nonce_hex": nonce.hex(),
            "ciphertext_hex": ciphertext_with_tag.hex(),
            "aad_binding": aad.decode("utf-8")
        }

    def decrypt_telemetry(self, packet: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        Decrypts and authenticates incoming packet.
        Enforces anti-replay verification and AEAD tag authentication.
        """
        astronaut_id = packet.get("astronaut_id")
        timestamp_ms = packet.get("timestamp_ms")
        seq_num = packet.get("seq_num")
        nonce_hex = packet.get("nonce_hex")
        ciphertext_hex = packet.get("ciphertext_hex")

        if not all([astronaut_id, timestamp_ms, seq_num is not None, nonce_hex, ciphertext_hex]):
            return False, None, "MALFORMED_PACKET_HEADER"

        # Anti-Replay check
        if not self._check_and_update_replay_window(seq_num):
            logger.warning("[SECURITY] Replay attack detected or duplicate packet: seq %d", seq_num)
            return False, None, "REPLAY_ATTACK_REJECTED"

        try:
            nonce = bytes.fromhex(nonce_hex)
            ciphertext = bytes.fromhex(ciphertext_hex)
            aad = f"{astronaut_id}:{timestamp_ms}:{seq_num}".encode("utf-8")

            # AES-GCM decrypt will raise InvalidTag if ciphertext or AAD was tampered
            decrypted_bytes = self._aesgcm.decrypt(nonce, ciphertext, aad)
            payload = json.loads(decrypted_bytes.decode("utf-8"))
            return True, payload, "OK"
        except Exception as exc:
            logger.error("[SECURITY] Decryption/Authentication failure: %s", str(exc))
            return False, None, f"AUTHENTICATION_TAG_VERIFICATION_FAILED: {str(exc)}"

    def _check_and_update_replay_window(self, seq: int) -> bool:
        """Sliding window anti-replay verification."""
        if seq in self._seen_seqs:
            return False

        if seq > self._highest_seq:
            self._highest_seq = seq
            self._seen_seqs.add(seq)
            # Prune old sequence numbers outside the window
            cutoff = self._highest_seq - self._replay_window_size
            self._seen_seqs = {s for s in self._seen_seqs if s > cutoff}
            return True
        elif seq > (self._highest_seq - self._replay_window_size):
            self._seen_seqs.add(seq)
            return True
        else:
            # Packet is too old
            return False

    def generate_auth_token(self, astronaut_id: str, role: str = "EVA_CREW", ttl_sec: int = 3600) -> str:
        """Generates an HMAC-SHA256 authenticated suit access token."""
        now = int(time.time())
        exp = now + ttl_sec
        token_payload = {
            "astronaut_id": astronaut_id,
            "role": role,
            "iat": now,
            "exp": exp,
            "rand": os.urandom(8).hex()
        }
        body_bytes = json.dumps(token_payload, sort_keys=True).encode("utf-8")
        sig = hmac.new(self._token_key, body_bytes, hashlib.sha256).hexdigest()
        return f"{body_bytes.hex()}.{sig}"

    def verify_auth_token(self, token_str: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """Validates HMAC-SHA256 token and verifies expiration using constant-time comparison."""
        parts = token_str.split(".")
        if len(parts) != 2:
            return False, None, "INVALID_TOKEN_FORMAT"

        body_hex, provided_sig = parts
        try:
            body_bytes = bytes.fromhex(body_hex)
            expected_sig = hmac.new(self._token_key, body_bytes, hashlib.sha256).hexdigest()

            # Constant-time comparison prevents timing attacks
            if not hmac.compare_digest(provided_sig, expected_sig):
                return False, None, "INVALID_SIGNATURE"

            token_data = json.loads(body_bytes.decode("utf-8"))
            if int(time.time()) > token_data.get("exp", 0):
                return False, None, "TOKEN_EXPIRED"

            return True, token_data, "AUTHENTICATED"
        except Exception as exc:
            return False, None, f"TOKEN_PARSE_ERROR: {str(exc)}"
