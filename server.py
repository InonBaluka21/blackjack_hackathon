import socket
import time
import threading
import subprocess
import ipaddress
import re

from game_controller import BlackjackGame
from protocol import ServerProtocol


class Server:
    def __init__(self):
        # setup TCP socket first (to get the port number)
        self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_sock.bind(("", 0))  # bind to any free port
        self.tcp_port = self.tcp_sock.getsockname()[1]  # get the assigned port
        self.tcp_sock.listen()

        # 2. setup UDP socket (for broadcasting the offer msg)
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        # Note: We don't bind UDP to 13122! we only send to 13122.
        self.is_running = True

        print(f"Server started, listening on IP address {self.get_local_ip()}")

    def get_local_ip(self):
        """
        Helper to print the actual IP (optional but useful)
        Connects to Google DNS to let the OS
        choose the active outgoing interface.
        """
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    def get_broadcast_address(self, ip):
        """
        Robustly finds the broadcast address.
        Fixes encoding crashes and supports university subnets.
        """
        if ip == "127.0.0.1":
            return "127.0.0.1"

        try:
            # FIX 1: errors='ignore' prevents the crash on Hebrew/Special chars
            output = subprocess.check_output("ipconfig", text=True, errors='ignore')
            
            mask = None
            lines = output.splitlines()
            
            # 2. Parse output
            for i, line in enumerate(lines):
                if ip in line:
                    # Look ahead a few lines for the mask
                    for j in range(1, 4):
                        if i + j < len(lines):
                            target_line = lines[i+j]
                            # We look for ANY line containing a mask-like pattern
                            # This bypasses the language issue (Works on Hebrew Windows too)
                            mask_match = re.search(r":\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", target_line)
                            
                            # Ensure it's not another IP (masks usually start with 255 or 0)
                            if mask_match:
                                candidate = mask_match.group(1)
                                if candidate.startswith("255."):
                                    mask = candidate
                                    break
                    if mask: 
                        break

            if not mask:
                # FIX 2: Your specific University fallback
                print(f"Warning: Could not auto-detect mask for {ip}. Using default.")
                mask = "255.255.255.0"  # Standard home default

            print(f"Detected Mask: {mask}")

            # 3. Calculate Broadcast
            net = ipaddress.IPv4Network(f"{ip}/{mask}", strict=False)
            return str(net.broadcast_address)

        except Exception as e:
            print(f"Error calculating broadcast: {e}")
            return "255.255.255.255" # Last resort fallback

    def broadcast_offers(self):
        """
        Runs in a background thread.
        Constantly announces the server's existence.
        """
        # get the IP the OS prefers
        my_ip = self.get_local_ip()

        # calculate the correct broadcast address for THAT network
        broadcast_ip = self.get_broadcast_address(my_ip)
        #broadcast_ip = "255.255.255.255"
        print(f"Server IP: {my_ip}")
        print(f"Broadcasting to: {broadcast_ip}")


        # Create the packet ONCE (optimization)
        packet = ServerProtocol.pack_offer("It hurts when IP", self.tcp_port)

        # Destination: broadcast IP + client's listening port (13122)
        dest = (broadcast_ip, 13122)

        while self.is_running:
            try:
                self.udp_sock.sendto(packet, dest)
                # print(f"Server sent offer announcing port {self.tcp_port}") # Debug only
                time.sleep(1)  # Broadcast every 1 second
            except Exception as e:
                print(f"Broadcast Error: {e}")

    def handle_client(self, client_sock):
        """
        Handles a single game session with a client.
        This runs in its own thread.
        """
        try:
            # receive client request msg (client asks to start a game)
            data = ServerProtocol.recv_all(client_sock, 38)
            if not data: return

            # parse request msg according to the protocol
            request = ServerProtocol.unpack_request(data)
            if not request:
                print("Invalid request received")
                return

            rounds, team_name = request
            print(f"Team {team_name} connected for {rounds} rounds.")

            # init game
            game = BlackjackGame(rounds)

            # define helper lambda to pack and send a drawn card during the game
            send_card = lambda card, status: client_sock.send(
                ServerProtocol.pack_game_state(status, card.rank, card.suit))

            # start the rounds
            while game.has_more_runs():
                player_card1, player_card2 = game.player_cards[:2]
                dealer_non_hidden_card, dealer_hidden_card = game.dealer_cards[:2]
                game_status = game.decide_game_status()

                # send the game setup
                send_card(player_card1, game_status)
                send_card(player_card2, game_status)
                send_card(dealer_non_hidden_card, game_status)

                while not game.is_player_busted:
                    # read the client payload msg and figure their decision
                    client_payload = ServerProtocol.recv_all(client_sock, 10)
                    # client_payload = client_sock.recv(1024)
                    client_decision = ServerProtocol.unpack_decision(client_payload)

                    # stop waiting for client commands when they sk to stand
                    if client_decision == ServerProtocol.CMD_STAND:
                        break

                    elif client_decision == ServerProtocol.CMD_HIT:
                        # player draws a card
                        player_drawn_card = game.player_hit()

                        # update game status
                        game_status = game.decide_game_status()

                        # send the move to the client
                        send_card(player_drawn_card, game_status)

                # here the client already finished his turn => it's the dealer's turn
                if not game.is_player_busted:
                    # now the dealer reveals the second card
                    # Note: game status shouldn't change at this point since this card has already been drawn
                    send_card(dealer_hidden_card, game_status)

                    # the dealer then draws additional cards
                    while not game.is_game_over:
                        # dealer draws a card
                        dealer_drawn_card = game.dealer_play()

                        # update game status
                        game_status = game.decide_game_status()

                        # send the move to the client
                        send_card(dealer_drawn_card, game_status)

                # NOTE:
                # here the current round is over
                # there is no need to check who won since it must be sent in every message
                # (i.e. we have already taken care of this)

                # prepare for the net round
                game.reset_game()

            # all rounds are over - show stats:
            game.statistics_print()

        except Exception as e:
            print(f"Error handling client: {e}")
        finally:
            client_sock.close()

    def start(self):
        # start UDP broadcast in a separate thread
        udp_thread = threading.Thread(target=self.broadcast_offers, daemon=True)
        udp_thread.start()

        # set a timeout of 1 second so accept() wakes up periodically
        self.tcp_sock.settimeout(1.0)

        # accept TCP connections in the main thread
        while self.is_running:
            try:
                client_sock, addr = self.tcp_sock.accept()
                print(f"New connection from {addr}")

                # create a thread for the new client so we can accept others
                client_thread = threading.Thread(target=self.handle_client, args=(client_sock,))
                client_thread.start()

            except socket.timeout:
                # handle the socket timeout by doing nothing
                # it allows us to stop blocking the process by listening non-stop and still keep the same flow
                # just loop back and check self.is_running again
                pass
            except KeyboardInterrupt:
                print("Closing connection")
                self.is_running = False
                break
            except Exception as e:
                print(f"Server Error: {e}")


if __name__ == '__main__':
    server = Server()
    server.start()