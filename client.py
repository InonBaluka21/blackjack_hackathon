import socket
import sys
import winsound
import os
from protocol import ClientProtocol
from deck import Card

class Client:
    def __init__(self):
        self.udp_port = 13122
        self.tcp_sock = None
        self.server_addr = None
        self.team_name = "It hurts when IP"
        self.wins = 0
        self.music_file = "bg_music.wav"

    def start_music(self):
        """
        Plays a wav file in the background (ASYNC) and loops it (LOOP).
        """
        if os.path.exists(self.music_file):
            # SND_FILENAME = The sound is a filename
            # SND_ASYNC    = Play in background (don't block code)
            # SND_LOOP     = Repeat forever
            try:
                winsound.PlaySound(
                    self.music_file,
                    winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP
                )
            except Exception as e:
                print(f"Audio error: {e}")

    def stop_music(self):
        """
        Stops the currently playing sound.
        """
        # Playing 'None' stops the current sound
        winsound.PlaySound(None, 0)

    def find_server(self):
        """
        Listens for UDP broadcast offers to find a server.
        Blocks until an offer is received.
        """
        print("Client started, listening for offer requests...")

        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Allow multiple clients on the same machine
        try:
            # Linux/Mac require SO_REUSEPORT flag to allow multiple clients on port 13122
            udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except AttributeError:
            # Windows doesn't support SO_REUSEPORT.
            # However, SO_REUSEADDR usually achieves the same result for this case.
            udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Bind to the udp server port
        udp_sock.bind(("", self.udp_port))

        # set timeout so we don't block forever (when receiving bytes)
        udp_sock.settimeout(1.0)

        while True:
            try:
                data, addr = udp_sock.recvfrom(1024)

                # extract server IP address
                # We use addr[0] because socket.recvfrom() returns a tuple: (data, address).
                # 'address' itself is a tuple: (ip_address, port_number).
                # We extract the IP from this header to ensure we connect back to the correct machine.
                # Source: https://docs.python.org/3/library/socket.html#socket.socket.recvfrom
                self.server_addr = addr[0]

                # Try to unpack the offer
                offer = ClientProtocol.unpack_offer(data)
                if offer:
                    tcp_server_port, server_name = offer
                    print(f"Received offer from {server_name} at {self.server_addr}")

                    # Return the server's IP (from UDP packet) and TCP port (from payload)
                    return self.server_addr, tcp_server_port

            # handle the timeout (just loop again)
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Error parsing UDP packet: {e}")

    def connect_and_play(self, ip, port, rounds=1):
        """
        Connects to the server via TCP and manages the game session.
        """
        try:
            self.start_music()

            self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_sock.connect((ip, port))
            print(f"Connected to server at {ip}:{port}")

            # 1. Send Request (Team Name + Rounds)
            req_packet = ClientProtocol.pack_request(self.team_name, rounds)
            self.tcp_sock.send(req_packet)

            # reset wins for this new session
            self.wins = 0

            # 2. Loop for each round
            for round_num in range(1, rounds + 1):
                # we check the return value of play_round to see if the connection died
                if not self.play_round(round_num):
                    break

            # 3. Print stats
            # Avoid division by zero if something crashed early
            win_rate = (self.wins / rounds) * 100 if rounds > 0 else 0
            print("-" * 30)
            print(f"Finished playing {rounds} rounds, win rate: {win_rate:.2f}%")
            print("-" * 30)

        except Exception as e:
            # This block catches Server Crashes / Disconnects
            print(f"\n[!] Server disconnected or error occurred: {e}")
            print("[*] Returning to listener mode...")
        finally:
            if self.tcp_sock:
                self.tcp_sock.close()
                self.tcp_sock = None  # Reset socket

            self.server_addr = None
            self.stop_music()
            print("Game finished. Connection closed.")

    def play_round(self, round_num):
        # track if the round is still active
        round_active = True
        player_total_points = 0
        deck_total_points = 0

        print(f"\n--- Round {round_num} Started ---")

        # --- Phase 1: Initial Deal (Receive 3 cards) ---
        # The server sends: 2 cards for me (the client), 1 dealer card.
        # We must read all 3 before asking for input.
        for i in range(3):
            if not self.receive_game_update(is_player=(i<2), wait_for_input=False):
                return False # connection died or Game Over immediately

        # --- Phase 2: Player Turn ---
        # my_turn = True
        while round_active:
            print("Your options: [1] Hit  [2] Stand")
            try:
                choice = int(input("Enter choice: "))
            except ValueError:
                print("Please enter a number (1 or 2).")
                continue  # skip to next loop iteration to ask again

            if choice == 1:
                # Send HIT
                self.tcp_sock.send(ClientProtocol.pack_decision(ClientProtocol.CMD_HIT))

                # Wait for the new card
                # If status becomes != 0 (Bust), receive_game_update returns False
                if not self.receive_game_update(is_player=True, wait_for_input=True):
                    round_active = False  # Round over (Bust)

            elif choice == 2:
                # Send STAND
                self.tcp_sock.send(ClientProtocol.pack_decision(ClientProtocol.CMD_STAND))
                #my_turn = False  # End my turn, wait for dealer
                break
            else:
                print("Invalid input. Please enter 1 or 2.")

        # --- Phase 3: Dealer Turn ---
        # If the round isn't over yet (I stood, didn't bust), watch dealer play
        # We loop until the server sends a Game Over status
        if round_active:
            while True:
                # We just listen. We pass 'False' because we don't need user input.
                # receive_game_update will return False when status != 0 (Win/Loss/Tie)
                if not self.receive_game_update(is_player=False, wait_for_input=False):
                    break

        return True  # Round finished successfully

    def receive_game_update(self, is_player, wait_for_input):
        """
        Helper: Reads one packet from server, prints the card/status.
        Returns:
            True if the round continues (Status == 0)
            False if the round ended (Status != 0)
        """
        try:
            # receive exactly 9 bytes (length of the server msg)
            data = ClientProtocol.recv_all(self.tcp_sock, 9)
            if not data: return False

            # unpack msg to extract its info
            result, rank, suit = ClientProtocol.unpack_game_state(data)
            card = Card(rank, suit)
            if is_player:
                print(f"You got: {card}. Value: {card.value}")
            else:
                print(f"Dealer got: {card}. Value: {card.value}")

            # when game is over
            if result != 0:
                outcomes = {1: "It's a Tie!", 2: "You Lost!", 3: "You Won!"}
                print(f"Round Result: {outcomes.get(result, 'Unknown')}")

                # if client wins, count it
                if result == 3:
                    self.print_winner()
                    self.wins += 1

                elif result == 2:
                    self.print_loser()

                return False  # Stop loop

            return True  # Keep playing

        except Exception as e:
            print(f"Error receiving data: {e}")
            return False

    def print_winner(self):
        print(r"""
      __   __  ___   _   _     __        ______  _   _   _ 
      \ \ / / / _ \ | | | |    \ \      / / __ \| \ | | | |
       \ V / | | | || | | |     \ \ /\ / / |  | |  \| | | |
        | |  | |_| || |_| |      \ V  V /| |  | | . ` | | |
        |_|   \___/  \___/        \_/\_/  \____/|_| \_| |_|

              .------.      .------.      
              |A .   |      |K  .  |      
              | / \  |      | /\   |      
              |(_,_) |      | \/   |      
              |  I   |      |  I   |      
              `------'      `------'      
           WINNER WINNER CHICKEN DINNER!
           """)

    def print_loser(self):
        print(r"""
      _____          __  __ ______    ______      ________ _____  
     / ____|   /\   |  \/  |  ____|  / __ \ \    / /  ____|  __ \ 
    | |  __   /  \  | \  / | |__    | |  | \ \  / /| |__  | |__) |
    | | |_ | / /\ \ | |\/| |  __|   | |  | |\ \/ / |  __| |  _  / 
    | |__| |/ ____ \| |  | | |____  | |__| | \  /  | |____| | \ \ 
     \_____/_/    \_\_|  |_|______|  \____/   \/   |______|_|  \_\

                      Better luck next time!
           """)

if __name__ == '__main__':
    client = Client()

    try:
        while True:
            # find server
            server_ip, server_port = client.find_server()

            num_of_rounds = int(input("Enter number of rounds: "))

            # play x rounds
            client.connect_and_play(server_ip, server_port, rounds=num_of_rounds)

    except KeyboardInterrupt:
        print("\nBye client!")
        if client.tcp_sock:
            client.tcp_sock.close()
        sys.exit(0)