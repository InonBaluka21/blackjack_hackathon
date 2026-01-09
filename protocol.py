import struct
import socket

class BlackjackProtocol:
    """
    Base class containing shared constants and validation logic.
    Do not use this class directly for packing/unpacking.
    """
    # --- Shared Constants ---
    MAGIC_COOKIE = 0xabcddcba
    MSG_OFFER = 0x2
    MSG_REQUEST = 0x3
    MSG_PAYLOAD = 0x4

    # commands
    CMD_HIT = "Hittt"       # Must be 5 bytes
    CMD_STAND = "Stand"     # Must be 5 bytes

    MAX_NAME_LEN = 32

    # --- Helper Methods (private using the underscore) ---
    @staticmethod
    def _check_cookie(cookie):
        if cookie != BlackjackProtocol.MAGIC_COOKIE:
            raise ValueError("Invalid magic cookie")

    @staticmethod
    def _check_msg_type(msg_type, expected_type):
        if msg_type != expected_type:
            raise ValueError(f"Invalid message type! Expected {expected_type}, got {msg_type}")

    @staticmethod
    def _check_decision(decision: str):
        if decision != BlackjackProtocol.CMD_HIT and decision != BlackjackProtocol.CMD_STAND:
            raise ValueError(f"Invalid decision: {decision}")

    @staticmethod
    def _format_string(s: str):
        """Truncates to 32 chars or pads with null bytes."""
        if len(s) > BlackjackProtocol.MAX_NAME_LEN:
            s = s[:BlackjackProtocol.MAX_NAME_LEN]
        return s.encode('utf-8').ljust(32, b'\x00')

    @staticmethod
    def recv_all(sock: socket.socket, length: int) -> bytes:
        """
        Helper to ensure we get exactly 'length' bytes.
        Loops until the buffer is full.
        """
        data = b''
        while len(data) < length:
            try:
                chunk = sock.recv(length - len(data))
                if not chunk:
                    raise Exception("Socket connection broken")
                data += chunk
            except socket.error as e:
                raise Exception(f"Socket error: {e}")
        return data


class ServerProtocol(BlackjackProtocol):
    """
    Protocol methods used ONLY by the Server.
    """

    @staticmethod
    def pack_offer(server_name: str, server_port: int) -> bytes:
        """
        Broadcasts availability to clients (UDP).
        Format: cookie(4), type(1), port(2), server_name(32)
        """
        name_bytes = BlackjackProtocol._format_string(server_name)
        return struct.pack('!IBH32s',
                           BlackjackProtocol.MAGIC_COOKIE,
                           BlackjackProtocol.MSG_OFFER,
                           server_port,
                           name_bytes)

    @staticmethod
    def unpack_request(data: bytes):
        """
        Parses a connection request from a client (TCP).
        Format: Cookie(4), type(1), rounds(1), team_name(32)
        Returns: (rounds, team_name)
        """
        try:
            cookie, msg_type, rounds, team_name = struct.unpack('!IBB32s', data)
            BlackjackProtocol._check_cookie(cookie)
            BlackjackProtocol._check_msg_type(msg_type, BlackjackProtocol.MSG_REQUEST)
            return rounds, team_name.decode('utf-8').rstrip('\x00')
        except Exception as e:
            print(f"Protocol Error (Request): {e}")
            return None

    @staticmethod
    def pack_game_state(result: int, card_rank: int, card_suit: int) -> bytes:
        """
        Sends card/result to client (TCP).
        Format: cookie(4), type(1), result(1), rank(2), suit(1)
        Note: Rank is 2 bytes (H), Suit is 1 byte (B) - adds up to 3 total.
        """
        return struct.pack('!IBBHB',
                           BlackjackProtocol.MAGIC_COOKIE,
                           BlackjackProtocol.MSG_PAYLOAD,
                           result,
                           card_rank,
                           card_suit)

    @staticmethod
    def unpack_decision(data: bytes):
        """
        Parses 'Hittt' or 'Stand' from client (TCP).
        [cite_start]Format: cookie(4), type(1), decision(5)
        Returns: decision_string
        """
        try:
            cookie, msg_type, decision = struct.unpack('!IB5s', data)
            BlackjackProtocol._check_cookie(cookie)
            BlackjackProtocol._check_msg_type(msg_type, BlackjackProtocol.MSG_PAYLOAD)

            decoded_decision = decision.decode('utf-8')
            BlackjackProtocol._check_decision(decoded_decision)

            return decoded_decision
        except Exception as e:
            print(f"Protocol Error (Decision): {e}")
            return None


class ClientProtocol(BlackjackProtocol):
    """
    Protocol methods used ONLY by the Client.
    """

    @staticmethod
    def unpack_offer(data: bytes):
        """
        Parses a server's broadcast (UDP).
        Format: cookie(4), type(1), port(2), server_name(32)
        Returns: (server_port, server_name)
        """
        try:
            cookie, msg_type, port, name = struct.unpack('!IBH32s', data)
            BlackjackProtocol._check_cookie(cookie)
            BlackjackProtocol._check_msg_type(msg_type, BlackjackProtocol.MSG_OFFER)
            return port, name.decode('utf-8').rstrip('\x00')
        except Exception as e:
            # Silent fail is common for UDP noise, but printing helps debugging
            print(f"Protocol Error (Offer): {e}")
            return None

    @staticmethod
    def pack_request(team_name: str, rounds: int) -> bytes:
        """
        Sends connection request to server (TCP).
        Format: cookie(4), type(1), rounds(1), team_name(32)
        """
        name_bytes = BlackjackProtocol._format_string(team_name)
        return struct.pack('!IBB32s',
                           BlackjackProtocol.MAGIC_COOKIE,
                           BlackjackProtocol.MSG_REQUEST,
                           rounds,
                           name_bytes)

    @staticmethod
    def pack_decision(decision: str) -> bytes:
        """
        Sends 'Hittt' or 'Stand' to server (TCP).
        Format: cookie(4), type(1), decision(5)
        """
        BlackjackProtocol._check_decision(decision)
        decision_bytes = decision.encode('utf-8')

        return struct.pack('!IB5s',
                           BlackjackProtocol.MAGIC_COOKIE,
                           BlackjackProtocol.MSG_PAYLOAD,
                           decision_bytes)

    @staticmethod
    def unpack_game_state(data: bytes):
        """
        Parses card/result from server (TCP).
        Format: cookie(4), type(1), result(1), rank(2), suit(1)
        Returns: (result, rank, suit)
        """
        try:
            cookie, msg_type, result, rank, suit = struct.unpack('!IBBHB', data)
            BlackjackProtocol._check_cookie(cookie)
            BlackjackProtocol._check_msg_type(msg_type, BlackjackProtocol.MSG_PAYLOAD)
            return result, rank, suit
        except Exception as e:
            print(f"Protocol Error (Game State): {e}")
            return None